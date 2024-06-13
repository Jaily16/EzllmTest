import os

import pytest


def test_file_path():
    path = "/111/test"
    filepath = "2023SEE_ch05.lecture-software cost metrics & control.pdf"
    filename = filepath.rsplit('.', 1)[0]
    postfix = os.path.splitext(filepath)[-1]
    print(postfix)
    filename = filename.replace(" ", "-")
    filename = filename.replace(".", "_")
    print(filename)
    new_path = filename + postfix
    filepath = os.path.join(path, new_path)
    print(filepath)
