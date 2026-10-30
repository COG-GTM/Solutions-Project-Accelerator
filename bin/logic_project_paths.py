import os
import re

PROJECTS_DIR = './projects'
MAX_PROJECT_NAME_LENGTH = 100

_PROJECT_NAME_PATTERN = re.compile(r'[\w .()-]{1,%d}' % MAX_PROJECT_NAME_LENGTH)
_WINDOWS_RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL',
                           *('COM%d' % i for i in range(1, 10)),
                           *('LPT%d' % i for i in range(1, 10))}


class InvalidProjectName(ValueError):
    pass


def is_valid_project_name(name):
    """
    Check that a project name is a plain folder name that cannot escape the projects folder.

    Allowed: letters, digits, underscore, space, '.', '(', ')' and '-', up to 100 characters.
    Rejected: '.', '..', leading/trailing spaces or dots, and Windows reserved device names.
    """
    if not isinstance(name, str) or not _PROJECT_NAME_PATTERN.fullmatch(name):
        return False
    if name != name.strip(' .') or name.startswith('.'):
        return False
    if name.split('.')[0].upper() in _WINDOWS_RESERVED_NAMES:
        return False
    return True


def validate_project_name(name):
    if not is_valid_project_name(name):
        raise InvalidProjectName(
            "Invalid project name %r. Use up to %d letters, digits, spaces, '_', '-', '.', '(' or ')'."
            % (name, MAX_PROJECT_NAME_LENGTH))
    return name


def projects_root():
    return os.path.abspath(PROJECTS_DIR)


def is_inside(root, path):
    """True if path is root itself or anywhere below it."""
    root = os.path.normcase(os.path.abspath(root))
    path = os.path.normcase(os.path.abspath(path))
    try:
        return os.path.commonpath([root, path]) == root
    except ValueError:  # different drives on Windows
        return False


def is_link(path):
    """True for symlinks and (on Windows) directory junctions."""
    isjunction = getattr(os.path, 'isjunction', None)
    return os.path.islink(path) or bool(isjunction and isjunction(path))


def project_dir(name):
    """
    Absolute path of the folder for project ``name``, guaranteed to be a direct child of ./projects.

    :raises InvalidProjectName: if the name is not a plain folder name, or the existing
        folder is a symlink/junction that resolves outside the projects folder.
    """
    validate_project_name(name)
    root = projects_root()
    destination = os.path.abspath(os.path.join(root, name))
    if os.path.dirname(destination) != root or not is_inside(root, destination):
        raise InvalidProjectName("Project folder for %r is outside the projects folder." % name)
    if is_link(destination) or not is_inside(os.path.realpath(root), os.path.realpath(destination)):
        raise InvalidProjectName("Project folder for %r is a link; refusing to use it." % name)
    return destination
