
# Modifying the behaviour of hashing

[todo]

For most python objects, the built-in hitsave hashing function will be good enough. However there are some cases where you may want to customise how an argument is hashed.

- Suppose that your argument is file path. Instead of hashing the filename, which depends on exactly where it is on your filesystem, you should hash the file itself.
- Some objects may not be suitable for hashing. An example is the `logging.Logger` object. This is only used to control logging and doesn't matter for the purposes of producing a value.

# Modifying the behaviour of saving

HitSave uses a customised version of python pickling.

[todo]

- By default `save` will also save the arguments of an evaluation to the server. You can control that with `@save(args = ...)`
- Some objects, for example standard datasets, do not need to be saved, because they are already present on disk or handled by pytorch's dataset downloader.

## Overriding pickling

[todo]