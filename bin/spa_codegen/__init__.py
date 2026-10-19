"""
SPA Code Generator Module

This module provides a fluent API for programmatically building HMI displays
using Control Modules, Static Graphics, and Display objects.

Usage:
    from spa_codegen import Display, ControlModule, StaticGraphic, ProcessLine
    
    display = (Display("Motor_Station", width=1920, height=1080)
        .add(ControlModule("PMTR", name="MTR-001").at(400, 300))
        .add(ControlModule("PVLV", name="XV-001").at(100, 300))
        .connect("XV-001.right", "MTR-001.left")
    )
    
    display.generate_gfx()
"""

from .objects import (
    CodeGeneratableObject,
    ControlModuleBuilder,
    StaticGraphicBuilder,
    DisplayBuilder,
    ProcessLineBuilder,
    AnchorPoint,
    AnchorDirection,
    AnchorType,
)

from .executor import (
    CodeExecutor,
    ExecutionMode,
    ExecutionResult,
    ValidationResult,
)

from .llm_generator import (
    LLMCodeGenerator,
)

# Convenience aliases for fluent API
ControlModule = ControlModuleBuilder
StaticGraphic = StaticGraphicBuilder
Display = DisplayBuilder
ProcessLine = ProcessLineBuilder

__all__ = [
    # Core objects
    'CodeGeneratableObject',
    'ControlModuleBuilder',
    'StaticGraphicBuilder', 
    'DisplayBuilder',
    'ProcessLineBuilder',
    'AnchorPoint',
    'AnchorDirection',
    'AnchorType',
    
    # Convenience aliases
    'ControlModule',
    'StaticGraphic',
    'Display',
    'ProcessLine',
    
    # Execution
    'CodeExecutor',
    'ExecutionMode',
    'ExecutionResult',
    'ValidationResult',
    
    # LLM
    'LLMCodeGenerator',
]

__version__ = '1.0.0'
