
from importlib.machinery import ModuleSpec


DocumentUri = str
ModuleName = str

class ProjectModule:
    """ A representation of a python module present in the project.

    In most cases, this represents a specific version of a python file in the user's project as it exists in the
    user's editor.

    A project module is analysed by hitsave for dependencies.
    """

    # the fully resolved module name of the file
    name : str
    # the LSP version of the sourcefile for this module.
    version : int
    # fully resolved uri of the sourcefile for this module (as given by LSP)
    # eg "file:///Users/edward/hitsave/project.py"
    # [warn] the contents of the file at the URI are not necessarily the up-to-date sourcetext that
    # this module represents. For example, an editor could have a version of the file in its buffer.
    uri : DocumentUri

    def __repr__(self):
        return self.name




class HSProject:
    """ This contains all of the state representing HitSave's view of the python files that we care about
    and things like python version etc.

    If we are running as a language server, the client editor can send didChange, didOpen, didClose notifications
    for certain files. As these files change, we need to update our own python runtime to reflect this.
    """

    def get_spec(module_name : ModuleName) -> ModuleSpec:


    def sourcetext(module_name : ModuleName) -> str:
        # [todo] make async
