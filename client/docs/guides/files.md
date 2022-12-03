(files)=
# Working with Files

When using HitSave, we recommend returning output computations directly as return values of your `@memo`ed functions.
However, there are also many usecases where you need to be able to store and retrieve files from disk as part of your data processing. For example, reading training images from an existing dataset or saving model weights.
However, using files creates some challenges for versioning your code and data, because your processing step now depends on the state of your filesystem.
To save and restore files in a reproducible way, HitSave uses __file snapshots__.

## Creating Snapshots

A file snapshot is a content-addressed blob of binary data that represents a file at a particular moment in time.

Let's see an example of using file snapshots. Consider the `write_hello` function below:

```python
from hitsave import memo
@memo
def write_hello(x : str):
    with open("hello.txt", 'wt') as f:
        f.write(x)
```

The return type of this function is `None`, so memoising this function won't do anything. We also don't capture the state of the `hello.txt` file, which mutates each time `write_hello` evaluates.
HitSave won't track which files a python function accesses for you, instead we need to tell HitSave which files a given function produces by creating file snapshots.

```python
from hitsave import FileSnapshot, memo
@memo
def write_hello(x : str) -> FileSnapshot:
    path = "hello.txt"
    with open(path, 'wt') as f:
        f.write(x)
    return FileSnapshot.snap(path)
```

What happens when we call {meth}`FileSnapshot.snap`?

1. The given file `hello.txt` is opened.
2. The [BLAKE3](https://github.com/BLAKE3-team/BLAKE3) digest and content length of the file contents is computed.
3. The file contents are copied to HitSave's local cache directory, with the file name being the hex representation of the digest. If the file is already present in the cache then no copying occurs.
4. The snapshot is flagged for uploading, and will later be uploaded to your cloud cache. You can force an immediate upload with {meth}`FileSnapshot.upload()`.

Now, even if later calls to `write_hello` cause `hello.txt` to change, we always have access to the file exactly as it appeared for each run.
The file data itself is not stored in the `FileSnapshot` object, instead only the `digest` and the path of the file relative to the project root is kept in memory. The file data is kept in the local cache.

## Restoring snapshots.

Suppose we make the following sequence of calls to `write_hello`:

```python
>>> write_hello("A")
# → writes "A" to hello.txt and returns a snaphshot of it
>>> write_hello("B")
# → writes "B" to hello.txt and returns a snaphshot of it
>>> write_hello("A")
# → "A" is cached, so returns the snapshot of hello.txt containing "A"
```

After calling `write_hello("A")` a second time, the contents of `hello.txt` on disk is still `B`.
`FileSnapshot` objects never manipulate file state without an explicit call to {meth}`restore()`.

```python
>>> write_hello("A").restore()
# WARN: file ~/demo/hello.txt already exists, replacing with a symlink ...
```

After calling `restore()`, `hello.txt` has been restored to contain `"A"`. Rather than directly copying the file, `hello.txt` is made a symlink to the content-addressed file on local disk.
`restore()` will warn you if you are about to overwrite an existing file, you can turn off the warning by passing `overwrite = True` as an argument. Restore returns a path to the newly restored file.
If you want to read the file without needing it to be in the exact location of the original file, you can run `restore_safe()` which will return a `Path` to the read-only cached snapshot file.

## Managing Snapshots

Snapshotting large files will fill up your cloud cache quickly, but we offer some tools for managing your storage.
HitSave tracks which evaluations created which file snapshots, and snapshots are automatically deleted if their corresponding evaluations are deleted. You can also manually delete snapshots from the 'blobs' tab of the dashboard. Furthermore, files with the same digest are only stored once, so you do not need to worry if you repeatedly snapshot the same file.

## Directory Snapshots

You can also take snapshots of entire directories with `DirectorySnapshot.snap("./my_dir/")`.
This recursively calls `FileSnapshot.snap()` for each file in the given directory (including subdirectories).
If a symlink is encountered, it is ignored and a warning is emitted.
The `DirectorySnapshot` object is stored as a list of all of the

## Snapshots for sharing files

A consequence of HitSave's filesnaphot system is that you can use it to share files.
In the CLI you can run

```sh
hitsave snapshot hello.txt
```

and hitsave will print a digest string. Other members of your team can then download this snapshot with

```sh
hitsave snapshot --restore DIGEST OUT_PATH
```

You can add the `--public` flag to make a publicly available snapshot. Please note before you share the digest link widely that there may be copyright and licencing implications for making files that you don't own the copyright for publically available.

## Snapshots for versioning datasets

You can use directory snapshots to version and distribute your datasets. Running

```
cd ~/datasets
hitsave snapshot my_cool_dataset/
```

Will return a digest (say `32684bfa28c`) that can be used to reliably reference a specific version of a dataset from within code.

```python
def load_dataset():
    dataset_snap = DirectorySnapshot.from_digest('32684bfa28c')
    dataset_path = dataset_snap.restore_safe()
    return MyCoolDatasetLoader(path = dataset_path)
```

Now, no matter where you run `load_dataset`, HitSave will download and restore the directory, or reuse the existing downloaded directory if `load_dataset` has already been run on this computer.
This is useful if you are processing data in an ephemeral docker container.
You can always be sure that the exact version of the data you need will be available.
You can avoid unnecessary redownloads by configuring the HitSave cache to be on a persistent volume.





