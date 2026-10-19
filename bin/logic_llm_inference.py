
"""
LLM Inference Module

This module provides unified interfaces for LLM inference using Ollama
(local/remote) and the public OpenAI API.

Key Features:
- Automatic environment detection for frozen executables
- Unified interface across providers
- Optional enterprise gateway support via the external ``genai_bridge``
  package (separate repository, configured through its own ``.env`` file).
  No enterprise endpoint, tenant, client ID or key lives in this repo; when
  ``genai_bridge`` is not installed or not configured, the app falls back to
  Ollama or a user-supplied public OpenAI key.
"""

import logging
import subprocess
import time
import os
import signal
import sys
import threading
import socket
import re
from typing import List, Tuple
import requests
import json
from pathlib import Path
import openai
import ollama
import textwrap


ollama_llm_base_url = ""


def _genai_bridge_source_roots():
    """Candidate directories holding an uninstalled ``genai_bridge`` package."""
    roots = []
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        roots.append(os.path.join(meipass, 'genai_bridge_src'))
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    roots.append(os.path.join(repo_root, 'genai_bridge', 'src'))
    return roots


def load_enterprise_inference_class():
    """
    Return the optional enterprise gateway client class, or ``None``.

    The implementation (MSAL auth, Key Vault certificates, APIM subscription
    key) lives in the separate ``genai_bridge`` repository and is configured
    through its own ``.env`` file. It is used when installed, or when its
    source tree sits next to this repo; otherwise callers must fall back to
    Ollama or the public OpenAI API.
    """
    for root in _genai_bridge_source_roots():
        if os.path.isdir(root) and root not in sys.path:
            sys.path.insert(0, root)
    try:
        from genai_bridge import InternalOpenAIInference
    except ImportError:
        return None
    except Exception as exc:  # noqa: BLE001 — a broken plugin must not break startup
        logging.warning("genai_bridge plugin failed to import: %s", exc)
        return None
    return InternalOpenAIInference


def is_frozen():
    """
    Check if the application is running as a frozen executable (e.g., PyInstaller)
    
    Returns:
        bool: True if application is frozen, False otherwise
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_nvidia_vram():
    """
    Get VRAM information for NVIDIA GPUs.
    
    Returns:
        dict: Dictionary containing GPU information with VRAM details
        None: If no NVIDIA GPUs found or nvidia-smi not available
    """
    try:
        # Run nvidia-smi command to get GPU information in JSON format
        result = subprocess.run([
            'nvidia-smi', 
            '--query-gpu=name,memory.total,memory.used,memory.free',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, check=True)
        
        gpu_info = {}
        lines = result.stdout.strip().split('\n')
        
        for i, line in enumerate(lines):
            if line.strip():
                parts = [part.strip() for part in line.split(',')]
                if len(parts) >= 4:
                    gpu_info[f'GPU_{i}'] = {
                        'name': parts[0],
                        'total_vram_mb': int(parts[1]),
                        'used_vram_mb': int(parts[2]),
                        'free_vram_mb': int(parts[3]),
                        'total_vram_gb': round(int(parts[1]) / 1024, 2),
                        'used_vram_gb': round(int(parts[2]) / 1024, 2),
                        'free_vram_gb': round(int(parts[3]) / 1024, 2)
                    }
        
        return gpu_info if gpu_info else None
        
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        # nvidia-smi not found or error running command
        return None
    

class OllamaInference:
    """
    Local Ollama inference implementation
    """

    MODEL_NAME = "reasoning:4b"
    MODEL_FILE_NAME = 'sha256-163553aea1b1de62de7c5eb2ef5afb756b4b3133308d9ae7e42e951d8d696ef5'
    
    def __init__(self, model_name=None, base_url=None, manage_server=True):
        """
        Initialize Ollama inference client

        :param model_name: Model to use for inference (defaults to ``MODEL_NAME``).
        :param base_url: Optional explicit base URL for a remote Ollama
            server (e.g. ``http://192.168.1.10:11434``). When provided the
            bundled server is NOT started.
        :param manage_server: When True (default) the bundled Ollama
            executable is started via ``Ollama_Manager``. Set False (or
            supply ``base_url``) to bypass and target an already-running
            server.
        """

        self.model_name = model_name if model_name else self.MODEL_NAME
        self.ollama_manager = None

        if base_url:
            # Remote / user-managed Ollama server. Do not touch the bundled
            # subprocess or the module-global ``ollama_llm_base_url``.
            self.base_url = base_url
        elif manage_server:
            self.ollama_manager = Ollama_Manager()
            self.ollama_manager.run()
            self.base_url = ollama_llm_base_url
        else:
            # Rely on whatever the module-global currently points at (may
            # have been set by an earlier bundled-server run).
            self.base_url = ollama_llm_base_url

        self.client = ollama.Client(host=self.base_url)

    def check_model(self):
        """
        Check if the model is available locally at Ollama/models/blobs/MODEL_FILE_NAME
        
        :return: True if model is available, False otherwise
        :rtype: bool
        """
        model_path = Path(f"Ollama/models/blobs/{self.MODEL_FILE_NAME}")
        return model_path.exists()

    
    def generate(self, prompt, model=None, temperature=0.7, max_tokens=None, stream=False, think=False):
        """
        Generate text using Ollama
        
        :param prompt: Input prompt
        :type prompt: str
        :param model: Model name (optional, uses default if not specified)
        :type model: str
        :param temperature: Sampling temperature
        :type temperature: float
        :param max_tokens: Maximum tokens to generate
        :type max_tokens: int
        :param stream: Whether to stream the response
        :type stream: bool
        :param think: Whether to enable thinking mode (disabled by default)
        :type think: bool
        :return: Generated text or stream

        """
        try:
            model_to_use = model or self.model_name
            
            options = {
                'temperature': temperature,
            }
            
            if max_tokens:
                options['num_predict'] = max_tokens
            
            if stream:
                return self.client.generate(
                    model=model_to_use,
                    prompt=prompt,
                    options=options,
                    stream=True,
                    think=bool(think)
                )
            else:
                response = self.client.generate(
                    model=model_to_use,
                    prompt=prompt,
                    options=options,
                    stream=False,
                    think=bool(think)
                )
                return response['response']
                
        except Exception as e:
            raise Exception(f"Ollama inference error: {str(e)}")

    def chat(self, messages, model=None, temperature=0.7, max_tokens=None, stream=False, think=False):
        """
        Chat completion using Ollama
        
        :param messages: List of message dicts with 'role' and 'content'
        :type messages: list
        :param model: Model name (optional, uses default if not specified)
        :type model: str
        :param temperature: Sampling temperature
        :type temperature: float
        :param max_tokens: Maximum tokens to generate
        :type max_tokens: int
        :param stream: Whether to stream the response
        :type stream: bool
        :param think: Whether to enable thinking mode (disabled by default)
        :type think: bool
        :return: Generated text or stream
        """
        try:
            model_to_use = model or self.model_name
            
            options = {
                'temperature': temperature,
            }
            
            if max_tokens:
                options['num_predict'] = max_tokens
            
            if stream:
                return self.client.chat(
                    model=model_to_use,
                    messages=messages,
                    options=options,
                    stream=True,
                    think=bool(think)
                )
            else:
                response = self.client.chat(
                    model=model_to_use,
                    messages=messages,
                    options=options,
                    stream=False,
                    think=bool(think)
                )
                return response['message']['content']
                
        except Exception as e:
            raise Exception(f"Ollama chat error: {str(e)}")
    
    
    def pull_model(self, model_name):
        """
        Pull/download a model
        
        :param model_name: Name of the model to download
        :type model_name: str
        :return: Success status
        :rtype: bool
        """
        try:
            self.client.pull(model_name)
            return True
        except Exception as e:
            raise Exception(f"Error pulling model {model_name}: {str(e)}")
        

    def list_models(self):
        """
        List available models
        
        :return: List of model names
        :rtype: list
        """
        try:
            return self.ollama_manager.list_models()
        except Exception as e:
            logging.error(f"Error listing models: {str(e)}")
            return []


class PublicOpenAIInference:
    """
    OpenAI-compatible inference using a user-supplied API key.

    Targets the public OpenAI endpoint (or any OpenAI-compatible proxy set
    via ``base_url``). This class deliberately does NOT touch MSAL, Azure
    Key Vault, or enterprise-gateway subscription-key headers — those code
    paths live in the optional ``genai_bridge`` package.

    Constructed by :class:`UnifiedInference` when the settings dialog's
    provider is ``openai`` and a DPAPI-decrypted key is available.
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key, base_url=None, organization=None,
                 model_name="gpt-4.1-mini"):
        if not api_key:
            raise ValueError("PublicOpenAIInference requires a non-empty api_key")
        self.api_key = api_key
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.organization = organization or None
        self.model_name = model_name

        client_kwargs = {'api_key': self.api_key, 'base_url': self.base_url}
        if self.organization:
            client_kwargs['organization'] = self.organization
        self._client = openai.OpenAI(**client_kwargs)

    def generate(self, prompt, model=None, temperature=0.7, max_tokens=None, stream=False):
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, model=model, temperature=temperature,
                         max_tokens=max_tokens, stream=stream)

    def chat(self, messages, model=None, temperature=None, max_tokens=None,
             stream=False, think=None):
        """
        Chat completion via the public OpenAI SDK.

        Returns the assistant string for non-streaming calls, or a generator
        yielding content chunks when ``stream=True``.
        """
        model_to_use = model or self.model_name
        payload = {'model': model_to_use, 'messages': messages, 'stream': stream}
        if temperature is not None:
            payload['temperature'] = temperature
        if max_tokens is not None:
            # openai>=1.x uses max_completion_tokens for newer models but
            # still accepts max_tokens for chat/completions. Prefer the
            # broadly-supported name.
            payload['max_tokens'] = max_tokens

        try:
            response = self._client.chat.completions.create(**payload)
        except openai.APIConnectionError as exc:
            raise requests.exceptions.ConnectionError(str(exc)) from exc
        except openai.APIError as exc:
            raise Exception(f"OpenAI chat error: {exc}") from exc

        if stream:
            return self._handle_stream_response(response)
        try:
            return response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise Exception("No response content received") from exc

    def _handle_stream_response(self, response):
        for chunk in response:
            try:
                delta = chunk.choices[0].delta
            except (AttributeError, IndexError):
                continue
            content = getattr(delta, 'content', None)
            if content:
                yield content

    def list_models(self):
        """Return a curated fallback list of public OpenAI model IDs; the
        Settings dialog refreshes this from ``/v1/models`` when a key is
        available."""
        return [
            "gpt-4.1-nano",
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-4o-mini",
            "gpt-4o",
        ]


class UnifiedInference:
    """
    Unified interface for both Ollama and OpenAI inference
    """
    
    def __init__(self, provider=None, **kwargs):
        """
        Initialize unified inference client
        
        :param provider: Inference provider ("ollama" or "openai"). Pass
            ``""`` / ``None`` together with ``config`` to auto-resolve from
            the user's saved settings (enterprise ``genai_bridge`` gateway
            when installed and configured, otherwise Ollama).
        :type provider: str
        :param config: Optional ``bin.logic_config.Config`` instance. When
            supplied, its LLM inference settings drive provider selection
            and are used to instantiate the public-OpenAI / remote-Ollama
            variants.
        :param kwargs: Provider-specific arguments forwarded to the
            underlying client(s). ``model_name`` from Config overrides any
            value passed here unless Config's value is empty.
        """
        config = kwargs.pop('config', None)
        self._config = config
        self._resolution = self._resolve_from_config(provider, config, kwargs)

        self.provider = self._resolution['provider']
        self.ollama_inference = None
        self.openai_inference = None
        self.raised_errors = {}
        self._init_lock = threading.Lock()
        self._kwargs = kwargs

        self.init_clients_done = False
        init_thread = threading.Thread(target=self.init_clients, daemon=True)
        init_thread.start()

        self.init_done_subscribers = []


    @staticmethod
    def _resolve_from_config(provider, config, kwargs):
        """
        Resolve which client backends to construct based on ``config``.

        Returns a dict with:
            - ``provider``: canonical provider name that ``init_clients``
              will select as the active client.
            - ``openai_mode``: ``"internal"`` (optional ``genai_bridge``
              enterprise gateway) or ``"public"`` (user-supplied API key
              via DPAPI store).
            - ``public_openai_kwargs``: kwargs for
              :class:`PublicOpenAIInference` (only set when mode = public).
            - ``ollama_kwargs``: kwargs for :class:`OllamaInference` (may
              carry a remote ``base_url``).
            - ``openai_model``: model_name override for the active OpenAI
              client, or ``None`` to keep caller-supplied default.

        ``UnifiedInference(provider="openai")`` with no ``config`` keeps
        openai_mode ``"internal"``. When ``config`` IS supplied but the user
        has no provider override, the resolver tries the enterprise gateway
        first and ``init_clients`` falls back to Ollama when the plugin is
        absent or unconfigured.
        """
        # Fallback provider when the caller didn't pass one:
        #   * no config  → "ollama" (matches the historical __init__ default)
        #   * config set → "openai" (enterprise gateway if available)
        default_provider = 'openai' if config is not None else 'ollama'
        resolution = {
            'provider': (provider or default_provider).lower(),
            'openai_mode': 'internal',
            'public_openai_kwargs': None,
            'ollama_kwargs': {},
            'openai_model': None,
        }

        if config is None:
            return resolution

        try:
            settings = config.get_llm_inference_settings()
        except Exception as exc:  # noqa: BLE001 — defensive; must not break startup
            logging.warning(
                "UnifiedInference: failed to read Config LLM settings (%s); "
                "falling back to legacy provider selection.", exc,
            )
            return resolution

        cfg_provider = (settings.get('provider') or '').strip().lower()

        # If no user override, keep the caller-supplied provider (enterprise
        # gateway path). Ollama kwargs still get any saved
        # ``ollama_model`` so the bundled default can be tuned without
        # switching providers.
        if not cfg_provider:
            ollama_model = (settings.get('ollama_model') or '').strip()
            if ollama_model:
                resolution['ollama_kwargs']['model_name'] = ollama_model
            return resolution

        if cfg_provider == 'openai':
            # Lazy import to avoid a hard dependency on the secret store
            # for modules that never touch inference (and to keep import
            # of logic_llm_inference cheap for pytest collection).
            try:
                from bin.logic_secret_store import load_openai_key
            except ImportError:
                from logic_secret_store import load_openai_key  # type: ignore[no-redef]

            api_key = load_openai_key()
            if api_key:
                resolution['provider'] = 'openai'
                resolution['openai_mode'] = 'public'
                model = (settings.get('openai_model') or '').strip() or 'gpt-4.1-mini'
                resolution['openai_model'] = model
                resolution['public_openai_kwargs'] = {
                    'api_key': api_key,
                    'base_url': (settings.get('openai_base_url') or '').strip() or None,
                    'organization': (settings.get('openai_organization') or '').strip() or None,
                    'model_name': model,
                }
            else:
                logging.warning(
                    "LLM provider set to 'openai' but no API key is stored; "
                    "falling back to legacy provider selection.",
                )
            return resolution

        if cfg_provider == 'ollama':
            resolution['provider'] = 'ollama'
            ollama_kwargs = {}
            model = (settings.get('ollama_model') or '').strip()
            if model:
                ollama_kwargs['model_name'] = model
            mode = (settings.get('ollama_mode') or 'bundled').strip().lower()
            if mode == 'remote':
                remote = (settings.get('ollama_remote_url') or '').strip()
                if remote:
                    ollama_kwargs['base_url'] = remote
                    ollama_kwargs['manage_server'] = False
                else:
                    logging.warning(
                        "Ollama mode is 'remote' but no URL is configured; "
                        "starting the bundled server instead.",
                    )
            resolution['ollama_kwargs'] = ollama_kwargs
            return resolution

        logging.warning(
            "Unknown LLM provider '%s' in config; falling back to legacy.",
            cfg_provider,
        )
        return resolution


    def init_done_subscribe(self, callback):
        """Subscribe to initialization done event"""
        self.init_done_subscribers.append(callback)

        if self.init_clients_done:
            callback()



    @staticmethod
    def _build_enterprise_client(kwargs):
        """Instantiate the optional ``genai_bridge`` client, or return ``None``."""
        cls = load_enterprise_inference_class()
        if cls is None:
            logging.info(
                "Enterprise LLM gateway plugin (genai_bridge) is not installed.",
            )
            return None
        try:
            return cls(**kwargs)
        except Exception as exc:  # noqa: BLE001 — unconfigured plugin is not fatal
            logging.info("Enterprise LLM gateway plugin unavailable: %s", exc)
            return None

    def init_clients(self):
        # Ollama client kwargs come from config resolution first, then any
        # caller-supplied kwargs (model_name, etc.) fill in the gaps. Never
        # forward Config-only kwargs (``config``) to the leaf classes.
        ollama_kwargs = dict(self._kwargs)
        ollama_kwargs.update(self._resolution.get('ollama_kwargs') or {})
        self.ollama_inference = OllamaInference(**ollama_kwargs)

        openai_mode = self._resolution.get('openai_mode', 'internal')
        if openai_mode == 'public':
            public_kwargs = dict(self._resolution.get('public_openai_kwargs') or {})
            self.openai_inference = PublicOpenAIInference(**public_kwargs)
        else:
            # Optional enterprise-gateway path (``genai_bridge``). Forward
            # caller kwargs (model_name etc.); do NOT forward ``base_url`` /
            # ``manage_server`` which are Ollama-only.
            enterprise_kwargs = {
                k: v for k, v in self._kwargs.items()
                if k not in {'base_url', 'manage_server'}
            }
            self.openai_inference = self._build_enterprise_client(enterprise_kwargs)

        if self.openai_inference is None and self.provider == 'openai':
            logging.info("No OpenAI backend available; falling back to Ollama.")
            self.provider = 'ollama'

        if self.provider == "ollama":
            self.client = self.ollama_inference
        elif self.provider == "openai":
            self.client = self.openai_inference
        else:
            raise ValueError(f"Unsupported provider: {self.provider}. Choose 'ollama' or 'openai'")

        ollama_list = {m: {'provider': 'ollama'} for m in self.ollama_inference.list_models()}
        openai_list = (
            {m: {'provider': 'openai'} for m in self.openai_inference.list_models()}
            if self.openai_inference is not None else {}
        )
        self.models_available = ollama_list | openai_list

        self.init_clients_done = True

        for callback in self.init_done_subscribers:
            callback()

        
    def switch_model(self, model_name):
        """Switch the provider and model"""
        provider = self.models_available.get(model_name, None).get('provider')
        self.raised_errors = {}
        if provider == "ollama":
            self.provider = "ollama"
            self.client = self.ollama_inference
            self.client.model_name = model_name
        elif provider == "openai":
            self.provider = "openai"
            self.client = self.openai_inference
            self.client.model_name = model_name
        else:
            raise ValueError(f"Unsupported provider: {provider}. Choose 'ollama' or 'openai'")
    
    def generate(self, prompt, **kwargs):
        """Generate text using the configured provider"""
        try:
            return self.client.generate(prompt, **kwargs)
        except requests.exceptions.RequestException as e:
            
            logging.error(f"Request error for model {self.get_model_name()}: {str(e)}")
            
            # Always propagate: swallowing the error returns ``None`` and the
            # caller then fails with a misleading AttributeError instead.
            self.raised_errors[self.get_model_name()] = str(e)
            raise

    def chat(self, messages, **kwargs):
        """Chat completion using the configured provider"""
        try:
            return self.client.chat(messages, **kwargs)
        except requests.exceptions.ConnectionError as e:
            raise 
        except requests.exceptions.RequestException as e:

            logging.error(f"Request error for model {self.get_model_name()}: {str(e)}")

            self.raised_errors[self.get_model_name()] = str(e)
            raise

    def get_provider(self):
        """Get the current provider name"""
        return self.provider
    

    def get_model_name(self):
        """Get the current model name"""
        return self.client.model_name
    
    def check_model(self):
        """Check if the model is available (only for Ollama)"""
        if self.provider == "ollama":
            return self.client.check_model()
        else:
            raise NotImplementedError("Model check is only implemented for Ollama provider")
        
    def get_all_models(self):
        """Get list of all available models"""

        return list(self.models_available.keys())

    def is_backend_ready(self):
        """
        Best-effort probe of whether the active backend is usable *now*.

        Returns True once the resolved backend has completed its handshake
        (MSAL for the enterprise gateway, immediate for user-key OpenAI,
        subprocess-start for bundled Ollama, TCP-reachable for remote
        Ollama). Callers use this to gate first-run hints without
        hard-coding environment heuristics.
        """
        if not self.init_clients_done:
            return False

        # User-supplied key path: constructor either succeeded or raised
        # ValueError. Nothing else to wait for.
        if self._resolution.get('openai_mode') == 'public' and self.provider == 'openai':
            return self.openai_inference is not None

        # Ollama: bundled server ran ``Ollama_Manager.run()`` during
        # ``OllamaInference.__init__``; the client object existing is the
        # closest sync signal we have without an extra network call.
        if self.provider == 'ollama':
            return self.ollama_inference is not None

        # Enterprise gateway path: wait for the async MSAL/KeyVault
        # handshake flag set inside the ``genai_bridge`` client.
        inf = self.openai_inference
        return bool(inf and getattr(inf, 'internal_api_auth_ok', False))

    def has_backend_check_completed(self):
        """
        True once we can give a definitive is/isn't-ready answer.

        Distinguishes "still trying" from "tried and failed" so callers can
        distinguish transient startup latency from a real misconfiguration.
        """
        if not self.init_clients_done:
            return False
        if self._resolution.get('openai_mode') == 'public' and self.provider == 'openai':
            return True
        if self.provider == 'ollama':
            return True
        inf = self.openai_inference
        return bool(inf and getattr(inf, 'internal_api_auth_attempted', False))





class Ollama_Manager:
    def __init__(self):
        self.ollama_path = r"Ollama"
        self.models_path = r"models"
        self.process = None
        self.running = False
        self.should_monitor = True
        self.default_port = 11434
        self.used_port = None

    
        
    def is_port_available(self, port):
        """Check if a port is available"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                return result != 0
        except Exception:
            return False
    
    def find_available_port(self, start_port=11434, max_attempts=50):
        """Find an available port starting from the given port"""
        for port in range(start_port, start_port + max_attempts):
            if self.is_port_available(port):
                return port
        return None
    
    def setup_environment(self):
        """Set up environment variables for Ollama"""
        os.environ['OLLAMA_MODELS'] = self.models_path
        
        # Check if default port is available
        if self.is_port_available(self.default_port):
            self.used_port = self.default_port
            logging.info(f"Using default port: {self.used_port}")
        else:
            logging.info(f"Default port {self.default_port} is occupied, finding alternative...")
            self.used_port = self.find_available_port(self.default_port + 1)
            
            if self.used_port is None:
                raise Exception("No available ports found in range")
            
            logging.info(f"Using alternative port: {self.used_port}")
            os.environ['OLLAMA_HOST'] = f"127.0.0.1:{self.used_port}"
        
        # Ensure models directory exists
        Path(self.models_path).mkdir(parents=True, exist_ok=True)
        
    def start(self):
        """Start the Ollama service"""
        global ollama_llm_base_url
        try:
            ollama_executable = os.path.join(self.ollama_path, "ollama.exe")
            if not os.path.exists(ollama_executable):
                logging.error(f"Error: Ollama executable not found at {ollama_executable}")
                return False
                
            logging.info(f"Starting Ollama with models path: {self.models_path}")
            logging.info(f"Service will be available on port: {self.used_port}")
            
            self.process = subprocess.Popen(
                [ollama_executable, "serve"],
                cwd=self.ollama_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                text=True,  # Ensure text mode for easier handling
                bufsize=1   # Line buffered
            )
            self.running = True

            # Start a thread to handle logging of subprocess output
            self._start_output_logging()

            ollama_llm_base_url = f"http://localhost:{self.used_port}"

            logging.info("Ollama service started successfully")
            return True
            
        except Exception as e:
            logging.error(f"Error starting Ollama: {e}")
            return False
        
    def _start_output_logging(self):
        """Start a thread to log subprocess output"""
        def log_output():
            if self.process and self.process.stdout:
                for line in iter(self.process.stdout.readline, ''):
                    if line.strip():  # Only log non-empty lines
                        # Parse Ollama log levels if present
                        # Convert bytes to string if necessary
                        #line = line.decode('utf-8', errors='ignore')
                        line_lower = line.lower()
                        
                        if 'error' in line_lower or 'fatal' in line_lower:
                            logging.error(f"Ollama: {line.strip()}")
                        elif 'warn' in line_lower or 'warning' in line_lower:
                            logging.warning(f"Ollama: {line.strip()}")
                        elif 'info' in line_lower:
                            logging.info(f"Ollama: {line.strip()}")
                        else:
                            logging.debug(f"Ollama: {line.strip()}")
                            
                    if not self.running:
                        break
        
        # Start the logging thread
        log_thread = threading.Thread(target=log_output, daemon=True)
        log_thread.start()
    
    def is_ollama_running(self):
        """Check if Ollama process is still running"""
        if self.process is None:
            return False
        return self.process.poll() is None
    
    def stop_ollama(self):
        """Stop the Ollama service gracefully"""
        self.should_monitor = False
        self.running = False
        
        if self.process:
            try:
                logging.info("Stopping Ollama service...")
                self.process.terminate()
                self.process.wait(timeout=10)
                logging.info("Ollama service stopped")
            except subprocess.TimeoutExpired:
                logging.info("Force killing Ollama service...")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                logging.error(f"Error stopping Ollama: {e}")

    def monitor_service(self):
        """Monitor the Ollama service and restart if it crashes"""
        while self.should_monitor:
            if self.running and not self.is_ollama_running():
                logging.warning("Ollama service stopped unexpectedly. Restarting...")
                self.running = False
                time.sleep(2)  # Brief delay before restart
                if self.should_monitor:  # Check if we should still monitor
                    self.start()
            time.sleep(5)  # Check every 5 seconds
    
    def list_models(self):
        """List all available models
        
        returns a list of model names
        """
        try:
            if not self.is_ollama_running():
                logging.warning("Ollama service is not running. Please start the service first.")
                return []
                
            ollama_executable = os.path.join(self.ollama_path, "ollama.exe")
            result = subprocess.run(
                [ollama_executable, "list"],
                capture_output=True,
                text=True,
                cwd=self.ollama_path
            )
            
            if result.returncode == 0:
                logging.info("\nAvailable Models:")
                logging.info("=" * 40)
                logging.info(result.stdout)

                models = []
                for line in result.stdout.strip().splitlines():
                    model = line.split()[0]
                    if model != "NAME":
                        models.append(model)

                return models
            else:
                logging.error(f"Error listing models: {result.stderr}")
                return []
                
        except Exception as e:
            logging.error(f"Error listing models: {e}")
            return []
        
    
    def show_model_info(self, model_name):
        """Show detailed information about a specific model"""
        try:
            if not self.is_ollama_running():
                logging.info("Ollama service is not running. Please start the service first.")
                return
                
            ollama_executable = os.path.join(self.ollama_path, "ollama.exe")
            result = subprocess.run(
                [ollama_executable, "show", model_name],
                capture_output=True,
                text=True,
                cwd=self.ollama_path
            )
            
            if result.returncode == 0:
                logging.info(f"\nModel Information for '{model_name}':")
                logging.info("=" * 40)
                logging.info(result.stdout)
            else:
                logging.error(f"Error getting model info: {result.stderr}")

        except Exception as e:
            logging.error(f"Error getting model info: {e}")


    def run(self):
        """Main execution method"""
        
        # Setup environment and start service
        try:
            self.setup_environment()
        except Exception as e:
            logging.error(f"Error during setup: {e}")
            return
        
        if not self.start():
            return
        
        # Start monitoring in a separate thread
        monitor_thread = threading.Thread(target=self.monitor_service, daemon=True)
        monitor_thread.start()

        logging.info("Ollama service is running.")
        logging.info(f"Models directory: {self.models_path}")
        logging.info(f"Service URL: {ollama_llm_base_url}")
        

def main():
    """Entry point"""
    print("Ollama LLM Inference Manager")
    print("=" * 40)
    
    manager = Ollama_Manager()
    manager.run()




def demo_inference():
    """
    Demonstrate inference against the optional enterprise gateway plugin
    """
    
    inference_cls = load_enterprise_inference_class()
    if inference_cls is None:
        print("genai_bridge is not installed; nothing to demo.")
        return

    openai_client = inference_cls(model_name="gpt-5-mini")
    

    test_prompt = textwrap.dedent(f"""\
        You are an expert in industrial automation. Extract parameter information from this SINGLE TABLE ROW with the table header.

        |Tag|Unit|Range|CtrlLo|CtrlLo|LoLo|Lo|Hi|HiHi|
        |WI00326|kg|0-2000|100|1800|50|200|1700|1900|

        Parameter hints: 
        - Val_EU_InpPV: (Val Engineering Unit) String e.g. %


        Extract:
        1. Tagname (instrument identifier like LIT1005, TIC3004)
        2. Parameter value (e.g. %)

        Respond in JSON format:
        {
            "extractions": [
                {
                    "tagname": "extracted_tagname",
                    "parameter_value": "value",
                    "confidence": 0.95
                }
            ]
        }

        If no parameters found, return {"extractions": []}.
        Response:""")

    print(f"\nTesting generation with model: {openai_client.model_name}")
    response = openai_client.generate(test_prompt, max_tokens=10000)
    print(f"Response: {response[:200]}...")

    test_messages = [
        {"role": "user", "content": "Tell me a story about a brave knight."}
    ]

    print(f"\nTesting chat completion:")
    chat_response = openai_client.chat(test_messages, max_tokens=10000)
    print(f"Chat response: {chat_response[:200]}...")
    
    print(f"\nTesting streaming chat:")
    print("Streaming response: ", end="")
    for chunk in openai_client.chat(test_messages, max_tokens=50, stream=True):
        print(chunk, end="", flush=True)
    print("\n")
                
        
    
    


def example_usage():
    """
    Example of how to use the optional enterprise gateway plugin
    """
    print("\n" + "=" * 50)
    print("OpenAI Inference Usage Example")
    print("=" * 50)
    
    inference_cls = load_enterprise_inference_class()
    if inference_cls is None:
        print("genai_bridge is not installed; nothing to demo.")
        return

    try:
        client = inference_cls(model_name="gpt-4o-mini")
        
        # Example 1: Simple text generation
        print("\n1. Simple text generation:")
        response = client.generate(
            "Write a short explanation of what a PLC is",
            max_tokens=150,
            temperature=0.7
        )
        print(f"Response: {response}")
        
        # Example 2: Chat completion with context
        print("\n2. Chat completion with context:")
        messages = [
            {"role": "system", "content": "You are an expert in industrial automation."},
            {"role": "user", "content": "What are the main benefits of using ACM (Application Code Manager)?"},
        ]
        
        chat_response = client.chat(
            messages,
            max_tokens=200,
            temperature=0.5
        )
        print(f"Chat response: {chat_response}")
        
        # Example 3: Streaming response
        print("\n3. Streaming response:")
        print("Streaming: ", end="", flush=True)
        for chunk in client.chat(
            [{"role": "user", "content": "List 3 advantages of batch processing in industrial automation"}],
            max_tokens=100,
            stream=True
        ):
            print(chunk, end="", flush=True)
        print("\n")
        
    except Exception as e:
        print(f"Example usage error: {e}")


if __name__ == "__main__":


    # Get detailed GPU information
    gpu_info = get_nvidia_vram()
    if gpu_info:
        print("NVIDIA GPU VRAM Information:")
        for gpu_id, info in gpu_info.items():
            print(f"\n{gpu_id}: {info['name']}")
            print(f"  Total VRAM: {info['total_vram_gb']} GB ({info['total_vram_mb']} MB)")
            print(f"  Used VRAM:  {info['used_vram_gb']} GB ({info['used_vram_mb']} MB)")
            print(f"  Free VRAM:  {info['free_vram_gb']} GB ({info['free_vram_mb']} MB)")
    else:
        print("No NVIDIA GPUs found or nvidia-smi not available")

    # Check what mode to run
    if len(sys.argv) > 1:
        if sys.argv[1] == "--demo":
            # Run inference demo
            demo_inference()
        elif sys.argv[1] == "--example":
            # Run usage example
            example_usage()
        else:
            print("Unknown option. Use --demo, --example, or --classifier")
    else:
        # Start the Ollama manager
        print("\nCommands:")
        print("  Type 'list' to show available models")
        print("  Type 'download <model_name>' to download a model")
        print("  Type 'help' for all commands")
        print("\nOptions:")
        print("  Run with '--demo' to test inference capabilities")
        print("  Run with '--example' to see usage examples")
        print("  Run with '--classifier' to test text classification")
        main()
    
