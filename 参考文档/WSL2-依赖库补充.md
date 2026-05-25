> 本文由 [简悦 SimpRead](http://ksria.com/simpread/) 转码， 原文地址 [github.com](https://github.com/opendatalab/MinerU/issues/388)

> Description of the bug | 错误描述 按最新一版 README 部署，报错：缺失依赖库。

[![](https://avatars.githubusercontent.com/u/62377256?u=c4cd01b5e9d5c34a8c019ed0c8f5f327fd75f467&v=4&size=80)](https://github.com/Ann5t)

Description
-----------

[![](https://avatars.githubusercontent.com/u/62377256?u=c4cd01b5e9d5c34a8c019ed0c8f5f327fd75f467&v=4&size=48)](https://github.com/Ann5t)[Ann5t](https://github.com/Ann5t)opened [on Aug 9, 2024](https://github.com/opendatalab/MinerU/issues/388#issue-2458373716)Issue body actions

### Description of the bug | 错误描述

按最新一版 README 部署，报错：缺失依赖库。

事后确认，主动安装缺失依赖库解决了问题。

```
sudo apt install libgl1-mesa-glx
```

### How to reproduce the bug | 如何复现

代码如下

```
sudo apt update && sudo apt upgrade -y && sudo apt install pip git-lfs -y

pip install magic-pdf[full]==0.7.0b1 --extra-index-url https://wheels.myhloli.com -i https://pypi.tuna.tsinghua.edu.cn/simple

git lfs clone https://www.modelscope.cn/wanderkid/PDF-Extract-Kit.git
```

magic-pdf.json 如下

```
{
    "bucket_info":{
        "bucket-name-1":["ak", "sk", "endpoint"],
        "bucket-name-2":["ak", "sk", "endpoint"]
    },
    "models-dir":"/home/user/PDF-Extract-Kit/models",
    "device-mode":"cpu",
    "table-config": {
        "is_table_recog_enable": false,
        "max_time": 400
    }
}
```

执行

```
magic-pdf -p small_ocr.pdf
```

报错

```
2024-08-10 01:32:12.420 | INFO     | magic_pdf.libs.pdf_check:detect_invalid_chars:57 - cid_count: 0, text_len: 8, cid_chars_radio: 0.0
2024-08-10 01:32:12.422 | WARNING  | magic_pdf.filter.pdf_classify_by_type:classify:334 - pdf is not classified by area and text_len, by_image_area: False, by_text: False, by_avg_words: False, by_img_num: True, by_text_layout: False, by_img_narrow_strips: False, by_invalid_chars: True
2024-08-10 01:32:12.442 | ERROR    | magic_pdf.model.pdf_extract_kit:<module>:27 - libGL.so.1: cannot open shared object file: No such file or directory
Traceback (most recent call last):

  File "/home/user/.local/bin/magic-pdf", line 8, in <module>
    sys.exit(cli())
    │   │    └ <Command cli>
    │   └ <built-in function exit>
    └ <module 'sys' (built-in)>
  File "/home/user/.local/lib/python3.10/site-packages/click/core.py", line 1157, in __call__
    return self.main(*args, **kwargs)
           │    │     │       └ {}
           │    │     └ ()
           │    └ <function BaseCommand.main at 0x712142210670>
           └ <Command cli>
  File "/home/user/.local/lib/python3.10/site-packages/click/core.py", line 1078, in main
    rv = self.invoke(ctx)
         │    │      └ <click.core.Context object at 0x7121426b3c10>
         │    └ <function Command.invoke at 0x712142211120>
         └ <Command cli>
  File "/home/user/.local/lib/python3.10/site-packages/click/core.py", line 1434, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           │   │      │    │           │   └ {'path': 'small_ocr.pdf', 'output_dir': '', 'method': 'auto'}
           │   │      │    │           └ <click.core.Context object at 0x7121426b3c10>
           │   │      │    └ <function cli at 0x7120cfc4ab00>
           │   │      └ <Command cli>
           │   └ <function Context.invoke at 0x7121421f7e20>
           └ <click.core.Context object at 0x7121426b3c10>
  File "/home/user/.local/lib/python3.10/site-packages/click/core.py", line 783, in invoke
    return __callback(*args, **kwargs)
                       │       └ {'path': 'small_ocr.pdf', 'output_dir': '', 'method': 'auto'}
                       └ ()
  File "/home/user/.local/lib/python3.10/site-packages/magic_pdf/tools/cli.py", line 75, in cli
    parse_doc(path)
    │         └ 'small_ocr.pdf'
    └ <function cli.<locals>.parse_doc at 0x712142455e10>
  File "/home/user/.local/lib/python3.10/site-packages/magic_pdf/tools/cli.py", line 60, in parse_doc
    do_parse(
    └ <function do_parse at 0x7121419d1090>
  File "/home/user/.local/lib/python3.10/site-packages/magic_pdf/tools/common.py", line 65, in do_parse
    pipe.pipe_analyze()
    │    └ <function UNIPipe.pipe_analyze at 0x7120cfc49f30>
    └ <magic_pdf.pipe.UNIPipe.UNIPipe object at 0x7120cfc39540>
  File "/home/user/.local/lib/python3.10/site-packages/magic_pdf/pipe/UNIPipe.py", line 31, in pipe_analyze
    self.model_list = doc_analyze(self.pdf_bytes, ocr=True)
    │    │            │           │    └ b'%PDF-1.7\r\n%\xa1\xb3\xc5\xd7\r\n1 0 obj\r\n<</Pages 2 0 R /Type/Catalog>>\r\nendobj\r\n2 0 obj\r\n<</Count 8/Kids[ 4 0 R  ...
    │    │            │           └ <magic_pdf.pipe.UNIPipe.UNIPipe object at 0x7120cfc39540>
    │    │            └ <function doc_analyze at 0x71210aa889d0>
    │    └ []
    └ <magic_pdf.pipe.UNIPipe.UNIPipe object at 0x7120cfc39540>
  File "/home/user/.local/lib/python3.10/site-packages/magic_pdf/model/doc_analyze_by_custom_model.py", line 109, in doc_analyze
    custom_model = model_manager.get_model(ocr, show_log)
                   │             │         │    └ False
                   │             │         └ True
                   │             └ <function ModelSingleton.get_model at 0x71210aa88940>
                   └ <magic_pdf.model.doc_analyze_by_custom_model.ModelSingleton object at 0x7120cf7201f0>
  File "/home/user/.local/lib/python3.10/site-packages/magic_pdf/model/doc_analyze_by_custom_model.py", line 63, in get_model
    self._models[key] = custom_model_init(ocr=ocr, show_log=show_log)
    │    │       │      │                     │             └ False
    │    │       │      │                     └ True
    │    │       │      └ <function custom_model_init at 0x71210aa88820>
    │    │       └ (True, False)
    │    └ {}
    └ <magic_pdf.model.doc_analyze_by_custom_model.ModelSingleton object at 0x7120cf7201f0>
  File "/home/user/.local/lib/python3.10/site-packages/magic_pdf/model/doc_analyze_by_custom_model.py", line 83, in custom_model_init
    from magic_pdf.model.pdf_extract_kit import CustomPEKModel
  File "<frozen importlib._bootstrap>", line 1027, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 688, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 883, in exec_module
  File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed
> File "/home/user/.local/lib/python3.10/site-packages/magic_pdf/model/pdf_extract_kit.py", line 9, in <module>
    import cv2
  File "/home/user/.local/lib/python3.10/site-packages/cv2/__init__.py", line 181, in <module>
    bootstrap()
    └ <function bootstrap at 0x7120cfc691b0>
  File "/home/user/.local/lib/python3.10/site-packages/cv2/__init__.py", line 153, in bootstrap
    native_module = importlib.import_module("cv2")
                    │         └ <function import_module at 0x71214250d750>
                    └ <module 'importlib' from '/usr/lib/python3.10/importlib/__init__.py'>
  File "/usr/lib/python3.10/importlib/__init__.py", line 126, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           │          │           │    │        │        └ 0
           │          │           │    │        └ None
           │          │           │    └ 0
           │          │           └ 'cv2'
           │          └ <function _gcd_import at 0x71214270f400>
           └ <module '_frozen_importlib' (frozen)>

ImportError: libGL.so.1: cannot open shared object file: No such file or directory
2024-08-10 01:32:12.452 | ERROR    | magic_pdf.model.pdf_extract_kit:<module>:28 - Required dependency not installed, please install by
"pip install magic-pdf[full] --extra-index-url https://myhloli.github.io/wheels/"
```

### Operating system | 操作系统

Windows

### Python version | Python 版本

3.10

### Software version | 软件版本 (magic-pdf --version)

0.6.x

### Device mode | 设备模式

cpu

Activity
--------

[![](https://avatars.githubusercontent.com/u/62377256?s=64&u=c4cd01b5e9d5c34a8c019ed0c8f5f327fd75f467&v=4)Ann5t](/Ann5t)added [bugSomething isn't working](/opendatalab/MinerU/issues?q=state%3Aopen%20label%3A%22bug%22)Something isn't working [on Aug 9, 2024](https://github.com/opendatalab/MinerU/issues/388#event-13823859501)

[![](https://avatars.githubusercontent.com/u/11393164?u=e9d5b4deeedaf4acb4c75c83a6d4863f206224da&v=4&size=80)](https://github.com/myhloli)

### myhloli commented on Aug 10, 2024

[![](https://avatars.githubusercontent.com/u/11393164?u=e9d5b4deeedaf4acb4c75c83a6d4863f206224da&v=4&size=48)](/myhloli)[myhloli](/myhloli)[on Aug 10, 2024](https://github.com/opendatalab/MinerU/issues/388#issuecomment-2282096335)CollaboratorMore actions

感谢反馈，我们会把这个案例加入 FAQ 中。

👍React with 👍1Ann5t

[![](https://avatars.githubusercontent.com/u/62377256?s=64&u=c4cd01b5e9d5c34a8c019ed0c8f5f327fd75f467&v=4)Ann5t](/Ann5t)closed this as [completed](/opendatalab/MinerU/issues?q=is%3Aissue%20state%3Aclosed%20archived%3Afalse%20reason%3Acompleted)[on Aug 10, 2024](https://github.com/opendatalab/MinerU/issues/388#event-13828000309)[![](https://avatars.githubusercontent.com/u/11393164?s=64&u=e9d5b4deeedaf4acb4c75c83a6d4863f206224da&v=4)myhloli](/myhloli)added a commit that references this issue [on Aug 10, 2024](https://github.com/opendatalab/MinerU/issues/388#event-13828747636)

[

docs(faq): add solution for libGL.so.1 missing on WSL2 Ubuntu22.04

](https://github.com/opendatalab/MinerU/commit/0405461d35c94ebdc7780c7c4e160322636886ea)...[0405461](https://github.com/opendatalab/MinerU/commit/0405461d35c94ebdc7780c7c4e160322636886ea)[![](https://avatars.githubusercontent.com/u/1788093?s=64&v=4)eagle-dai](/eagle-dai)added a commit that references this issue [on Aug 11, 2024](https://github.com/opendatalab/MinerU/issues/388#event-13840034195)

[

docs(faq): add solution for libGL.so.1 missing on WSL2 Ubuntu22.04

](https://github.com/eagle-dai/MinerU/commit/c4b050d8afee5d296f5e69abdd6283a9614cbbce)...[c4b050d](https://github.com/eagle-dai/MinerU/commit/c4b050d8afee5d296f5e69abdd6283a9614cbbce)

[![](https://avatars.githubusercontent.com/u/165017405?v=4&size=80)](https://github.com/iceberg2024)

### iceberg2024 commented on Jul 1, 2025

[![](https://avatars.githubusercontent.com/u/165017405?v=4&size=48)](/iceberg2024)[iceberg2024](/iceberg2024)[on Jul 1, 2025](https://github.com/opendatalab/MinerU/issues/388#issuecomment-3022801970)More actions

在 Ubuntu 的 24 版本 libgl1-mesa-glx 这个库已经更名为 libglx-mesa0，安装的时候需要执行的是  
sudo apt install libglx-mesa0  
直接装原来的，会提示找不到包

[![](https://avatars.githubusercontent.com/u/74045508?v=4&size=80)](https://github.com/lizepengg)

### lizepengg commented on Jul 18, 2025

[![](https://avatars.githubusercontent.com/u/74045508?v=4&size=48)](/lizepengg)[lizepengg](/lizepengg)[on Jul 18, 2025](https://github.com/opendatalab/MinerU/issues/388#issuecomment-3089022358)More actions

这个是在容器中安装还是主机上安装

[Sign up for free](/signup?return_to=https://github.com/opendatalab/MinerU/issues/388) **to join this conversation on GitHub.** Already have an account? [Sign in to comment](/login?return_to=https://github.com/opendatalab/MinerU/issues/388)