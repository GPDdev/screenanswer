# 框答 ScreenAnswer

框选屏幕中的题目，使用自己的 AI API，在可置顶的小窗里查看题目、答案和简要解析。

<div align="center"><img alt="Version 0.1.0" src="https://img.shields.io/badge/version-0.1.0-8de3c1"><img alt="Windows 10 and 11 x64" src="https://img.shields.io/badge/platform-Windows%2010%20%2F%2011%20x64-blue"><img alt="Python 3.10 or newer" src="https://img.shields.io/badge/Python-3.10%2B-3776AB"><img alt="9 local unit tests passed" src="https://img.shields.io/badge/local%20unit%20tests-9%20passed-success"><img alt="License not specified" src="https://img.shields.io/badge/license-not%20specified-lightgrey"></div>

<p align="center"><a href="https://github.com/GPDdev/screenanswer/releases/latest">下载 Windows 版</a> | <a href="#快速开始">快速开始</a> | <a href="#api-配置">API 配置</a> | <a href="https://github.com/GPDdev/screenanswer/issues">反馈问题</a></p>

适合学习、练习和资料阅读时查看解题参考。程序支持视觉模型直接读取截图，或 Windows 本地 OCR 提取文字后调用文本模型。接口、Key、模型和答题提示均由用户配置。

## 目录

- [功能](#功能)
- [界面预览](#界面预览)
- [快速开始](#快速开始)
- [使用方法](#使用方法)
- [API 配置](#api-配置)
- [自动扫描规则](#自动扫描规则)
- [数据与隐私](#数据与隐私)
- [从源码运行](#从源码运行)
- [测试与打包](#测试与打包)
- [项目结构](#项目结构)
- [常见问题](#常见问题)
- [已知限制](#已知限制)
- [参与贡献](#参与贡献)
- [许可证](#许可证)

## 功能

| 功能 | 说明 |
| --- | --- |
| 屏幕框选 | 鼠标拖动选择题目区域，松开确认，Esc 或右键取消。 |
| 两种识别方式 | 视觉模型读取截图；本地 OCR 提取文字后调用文本模型。 |
| 答案小窗 | 支持置顶、移动、缩放，展示题目、答案和简要解析。 |
| 自动扫描 | 观察固定区域，画面变化且稳定后请求新答案。 |
| 自定义 API | 配置 OpenAI 兼容接口的地址、Key、模型和答题提示。 |
| 请求控制 | 单任务运行、画面去重、超时设置、错误后暂停自动扫描。 |
| Key 保存 | 默认只在内存中使用，可选择通过 Windows DPAPI 加密保存。 |
| 题目预览 | 查看实际选中区域，OCR 模式可查看提取的文字。 |
| 快捷键与复制 | 支持全局快捷键和一键复制答案。 |
| 便携运行 | Release 提供 Windows x64 单文件 EXE，无需安装 Python。 |

## 界面预览

下图使用演示数据，未调用真实模型。截图只包含程序界面，不包含个人屏幕内容或真实 Key。

<p align="center"><img src="docs/images/main.png" alt="框答答案小窗，展示示例题目和答案" width="420"></p>

<details>
<summary>查看 API 设置界面</summary>

<p align="center"><img src="docs/images/settings.png" alt="API 设置，可填写接口、Key、模型和识别方式" width="600"></p>

</details>

## 快速开始

1. 从 [Releases](https://github.com/GPDdev/screenanswer/releases/latest) 下载 `ScreenAnswer.exe`。
2. 双击运行，打开右上角的「API 设置」。
3. 填写 API Base URL、API Key 和模型名称，选择识别方式，点击「保存」。
4. 点击「框选区域」，拖动选择题目。
5. 把框答小窗移到题目区域之外，点击「识别一次」。

需要连续识别时，勾选「自动扫描变化」。启动时不会自动扫描，也不会自动发出 API 请求。

运行要求：Windows 10 / 11 x64。OCR 模式还需要安装题目对应语言的 Windows OCR 组件。当前实际验证环境为 Windows 11，详见 [验证记录](TESTING.md)。

每个版本的 Release 同时提供 `SHA256SUMS.txt`，可用以下命令核对下载文件的 SHA-256：

```powershell
Get-FileHash .\ScreenAnswer.exe -Algorithm SHA256
```

## 使用方法

| 操作 | 方法 |
| --- | --- |
| 选择或重选区域 | 点击「框选区域」，或按 `Ctrl+Alt+Q`。 |
| 识别当前题目 | 点击「识别一次」，或按 `Ctrl+Alt+A`。 |
| 连续识别 | 勾选「自动扫描变化」，取消勾选即可暂停。 |
| 查看截图或 OCR 文字 | 打开「题目预览」标签页。 |
| 复制结果 | 点击「复制答案」。 |
| 调整置顶 | 切换「窗口置顶」。 |
| 修改回答风格 | 在 API 设置中修改「答题要求」。 |

快捷键被其他程序占用时，底部会提示，可继续使用窗口按钮。默认要求模型用中文给出题目、答案和简要解析，支持对一张截图中的多道题逐题回答。实际效果取决于所用模型。

## API 配置

采用 OpenAI 兼容的 **Chat Completions** 协议，发送 `POST /chat/completions`，通过 Bearer Key 认证，读取 `choices[0].message.content`。服务商原生的其他协议需要提供兼容入口。

| 配置项 | 说明 |
| --- | --- |
| API Base URL | 如 `https://api.example.com/v1`。程序追加 `/chat/completions`，也接受完整的 `/chat/completions` 地址。 |
| API Key | 填写自己的 Key；本地无鉴权服务可填写 `local` 等占位值。 |
| 模型名称 | 填写服务商实际支持的模型 ID。 |
| 识别方式 | 「视觉模型直接读图」或「本地 OCR + 文本模型」。 |
| 记住 Key | 默认关闭；开启后使用当前 Windows 账户加密保存。 |
| 扫描间隔 | 1–60 秒，默认 2 秒。需要连续两次采样稳定才请求。 |
| 超时 | 10–300 秒，默认 90 秒。 |
| 答题要求 | 自定义输出语言、详略、格式等，最多 10000 个字符。 |

远程接口使用 HTTPS。本机服务可使用 `http://localhost`、`http://127.0.0.1` 或 `http://[::1]`。使用系统代理设置，不跟随 HTTP 重定向；地址不能带账号、密码、查询参数或 URL 片段。

「测试连接」会发送一条简短文本请求，可能产生少量 API 用量，只验证连接和文本响应。视觉能力需要用实际题目截图验证；测试连接不会保存设置。

### 视觉模型直接读图

选中区域编码为 JPEG，随题目提示发送给模型。需要模型及接口支持 `image_url` 图片输入。适合公式、图表、几何图形或复杂排版，上传图片长边最多 2560 像素。

### 本地 OCR + 文本模型

使用 Windows 自带 OCR 在本地提取文字，只把提取结果发送给文本模型。识别语言按 Windows 用户语言配置选择，系统需要安装相应的 OCR 组件。公式、图表和复杂排版可能丢失，遇到这类题目建议切换视觉模式。

接口图片输入格式参考 [OpenAI 官方 Images and vision 文档](https://developers.openai.com/api/docs/guides/images-vision)。

## 自动扫描规则

- 只观察本次框选的固定区域；重启程序后需要重新选择。
- 使用局部画面差异检测，连续两次采样稳定后提交变化的画面。
- 同时最多处理一个识别任务，自动请求至少间隔 3 秒。
- 同一稳定画面不会持续调用 API；手动点击「识别一次」可再次请求。
- 小窗遮住题目时暂停采集，移开后恢复。框选区域尽量避开视频、动画和持续闪烁的输入光标。
- API 或 OCR 出错后关闭自动扫描，处理后可手动重试或重新开启。
- 取消扫描、重新框选或打开设置会丢弃旧任务结果。已发送的 HTTP 请求无法撤回，仍可能计费；尚未发送的 OCR 任务会在本地识别完成后取消。

## 数据与隐私

- 配置位于 `%APPDATA%\ScreenAnswer\config.json`。
- 默认不保存 Key。选择「记住 Key」后通过 Windows DPAPI 加密保存；取消勾选并保存会移除已保存的 Key。同一 Windows 账户下有权限的程序仍可能解密该数据。
- 视觉模式的截图仅在内存中处理。OCR 模式为调用系统组件会在系统临时目录写入 PNG，正常完成或报错后删除；强制终止进程可能留下临时文件。
- 不保存题目、答案或使用日志，不内置遥测。界面、截图预览和回答在程序运行期间保留于内存中。
- 触发答题时，所选区域截图或 OCR 文字会发送到用户配置的 API。点击「测试连接」会发送测试文字。服务商的数据处理规则由服务商决定。
- 复制答案会写入系统剪贴板，剪贴板历史或其他有权限的程序可能读取。
- 屏幕内容和模型回答仅作为文本展示，程序不会执行其中的命令。

## 从源码运行

需要 Python 3.10+，当前验证版本为 Python 3.13。运行依赖为 Pillow，界面使用 Python 自带的 Tkinter。

```powershell
git clone https://github.com/GPDdev/screenanswer.git
cd screenanswer

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m screenanswer
```

也可双击 `run.cmd`，脚本会使用 Windows Python Launcher 的 `py -3` 建立 `.venv`，按需安装 Pillow 后启动。首次安装依赖需要联网。已配置好脚本执行方式时也可运行 `run.ps1`。

## 测试与打包

### 运行测试

在已安装依赖的 Windows 环境中运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe -m tests.smoke_windows
```

单元测试使用本机模拟 API，不需要真实 Key。Windows 冒烟测试会打开程序自己的示例窗口，验证实际框选、截图、系统 OCR、模拟 API、取消、自动去重、复制和设置保存，需要交互式桌面及可用的 OCR 语言组件。

完整记录和验证范围见 [TESTING.md](TESTING.md)。

### 生成 EXE

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Python .\.venv\Scripts\python.exe
.\.venv\Scripts\python.exe -m tests.check_exe
```

输出为 `dist\ScreenAnswer.exe`。`tests.check_exe` 会启动并关闭刚生成的程序，使用独立的测试配置目录。当前提供未签名的单文件便携程序，没有安装器。

文档演示截图可使用 `python tools/capture_docs.py` 重新生成；该脚本只展示模拟数据，不调用 API。

## 项目结构

```text
screenanswer/
├── main.py                    # EXE 入口
├── screenanswer/
│   ├── app.py                 # 框选、设置、答案界面与任务调度
│   ├── core.py                # API 请求、画面去重与配置
│   ├── windows.py             # DPI、快捷键、DPAPI、OCR 调用
│   ├── ocr.ps1                # Windows OCR 桥接
│   └── __main__.py            # python -m screenanswer 入口
├── tests/                     # 单元测试与 Windows 冒烟测试
├── tools/capture_docs.py       # 生成无个人信息的演示截图
├── docs/images/               # README 界面截图
├── run.cmd / run.ps1           # 源码启动
├── build.ps1                  # Windows EXE 打包
├── requirements.txt           # 运行依赖
├── requirements-build.txt     # 打包依赖
└── TESTING.md                 # 已完成验证及范围
```

## 常见问题

| 问题 | 处理方式 |
| --- | --- |
| HTTP 400，模型不接受图片 | 检查模型和接口是否支持视觉输入，或切换本地 OCR 配合文本模型。 |
| HTTP 401 / 403 | 检查 Key 是否有效，以及账号、模型和接口权限。 |
| HTTP 404 | 核对 Base URL、`/v1` 路径和模型 ID。 |
| HTTP 429 | 检查服务商额度和频率限制，调整后手动重试。 |
| 接口返回重定向 | 直接填写最终的兼容接口地址。 |
| 本地 OCR 不可用 | 在 Windows 语言设置中安装所需语言的 OCR 组件，或切换视觉模式。 |
| 识别不到题目或文字错误 | 缩小区域、提高显示清晰度，复杂公式或图表优先使用视觉模型。 |
| 提示小窗遮住题目 | 把小窗移到框选区域之外。 |
| 自动扫描没有更新 | 确认仍勾选自动扫描、题目出现实际变化且画面稳定，没有错误导致暂停。 |
| API 超时 | 调高超时或换用响应更快的模型；也可检查网络与系统代理。 |
| 复制配置后 Key 无法解密 | DPAPI 保存的 Key 与 Windows 账户环境相关，在目标环境重新填写。 |

## 已知限制

- 真实服务商的模型准确率、响应时间、费用和兼容差异尚未验证。请自行核对模型答案。
- 当前实际测试为 Windows 11 单屏、200% 缩放；多屏、混合 DPI、远程桌面、受保护窗口和其他系统版本还需要实机验证。
- 固定区域不自动跟随题目移动；改变题目窗口布局后应重新框选。
- OCR 对公式、表格和图表的还原有限；自动变化检测也可能受到动画、滚动或闪烁影响。
- 当前一次性展示完整响应，尚未提供流式输出。
- 本项目不内置模型、API Key 或免费调用额度，不支持 macOS / Linux。

## 参与贡献

欢迎通过 [Issues](https://github.com/GPDdev/screenanswer/issues) 报告问题或提交 Pull Request。

问题报告建议包含 Windows 版本、缩放比例、识别方式、接口协议、模型 ID、错误提示和复现步骤。请不要上传 API Key、完整配置文件或含个人信息的屏幕截图。

修改程序逻辑时请补充相关测试，至少运行单元测试；涉及界面、框选或 OCR 时，请在 Windows 交互式桌面执行对应冒烟检查。文档、构建脚本和运行依赖应与实际实现保持一致。

## 许可证

当前尚未指定项目许可证。依赖库和打包工具保留各自的许可条款。
