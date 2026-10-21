# 框答 ScreenAnswer

框选屏幕中的题目，调用自己的 API，在可置顶的小窗里查看题目、答案和简要解析。适用于 Windows 10 / 11（64 位）。

## 直接使用

1. 双击 `dist/ScreenAnswer.exe`，无需安装 Python。
2. 打开「API 设置」，填写 API Base URL、API Key、模型名称并保存。默认地址仅为示例，模型名称需要自己填写。
3. 点击「框选区域」，拖动选择屏幕中的题目。松开确认，Esc 或右键取消。
4. 将框答小窗放在题目区域外，点击「识别一次」。答案会显示在「答案」标签页。
5. 如果需要连续识别，勾选「自动扫描变化」。程序会在区域画面稳定且有变化时自动请求；同一画面不会持续请求。

窗口可以移动、缩放和取消置顶。「题目预览」显示实际选中的区域；OCR 模式还会显示提取出的文字。「复制答案」复制当前生成的结果。

全局快捷键：`Ctrl+Alt+Q` 框选，`Ctrl+Alt+A` 识别一次。若快捷键被其他程序占用，窗口底部会提示，仍可使用按钮。

## API 配置

支持 OpenAI 兼容的 **Chat Completions** 协议，不是任意 API 格式。API 服务商、模型和 Key 由用户提供。

| 配置 | 示例与说明 |
| --- | --- |
| API Base URL | `https://your-provider.example/v1`，程序追加 `/chat/completions`。也可直接填写完整的 `/chat/completions` 地址。 |
| API Key | 服务商颁发的 Key；本地无鉴权服务可填写 `local` 等占位值。 |
| 模型名称 | 服务商实际支持的模型 ID，不能填产品的显示名称来代替。 |
| 识别方式 | 视觉模型直接读图，或本地 OCR + 文本模型。 |
| 扫描间隔 | 1–60 秒，默认 2 秒。需连续两次采样画面稳定才发送。 |
| 超时 | 10–300 秒，默认 90 秒。 |
| 答题要求 | 可修改输出语言、详略、解题格式等。 |

远程服务使用 HTTPS；本机 `http://localhost`、`http://127.0.0.1`、`http://[::1]` 可用于本地模型。支持系统代理，不允许接口重定向，避免 Key 被发送到其他地址。

「测试连接」会发出一条简短文本请求，可能产生少量 API 费用；它只能验证连接和文本响应，视觉能力需要用实际截图验证。测试不会自动保存设置。

### 视觉模型直接读图

将选定区域编码为 JPEG，随请求发送给视觉模型。适合含公式、图表、几何图形的题目。模型必须支持 `image_url` 图片输入。图片长边最多 2560 像素，题目过小或文字过密时请缩小框选范围。

### 本地 OCR + 文本模型

通过 Windows 自带的 OCR 提取文字，仅把文字发送到 API，可使用文本模型。系统需要安装题目对应语言的 OCR 组件，识别语言按 Windows 用户语言配置选择。公式、复杂排版和图表可能丢失，建议改用视觉模式。

## 自动扫描的行为

- 只观察本次选定的固定区域，重新启动后需要重新框选，不会自动开始扫描。
- 使用局部画面差异检测，等待连续两帧稳定，再发出请求。
- 同时最多进行一次识别任务；自动 API 请求至少间隔 3 秒。
- 自动扫描遇到 API / OCR 错误会暂停，避免持续消耗额度。手动处理后可重新打开。
- 小窗遮住题目时暂停采集，移开后自动恢复。请避开视频、动画和持续闪烁的输入光标。
- 取消自动扫描、重新框选或打开设置会丢弃旧任务的结果。已经发送的 HTTP 请求无法撤回，仍可能计费；尚未发送的 OCR 任务会在本地识别完成后取消。

## 数据保存

- 配置在 `%APPDATA%/ScreenAnswer/config.json`。
- 默认不保存 Key。勾选「记住 Key」后使用 Windows DPAPI 加密，只能由同一 Windows 账户解密；取消勾选并保存会移除已保存的 Key。
- 视觉模式截图仅存于内存。OCR 模式为调用系统识别组件会在系统临时目录写入一张 PNG，识别完成或报错后删除；进程被强制终止时可能留下临时文件。
- 不保存题目、答案或使用日志，不内置遥测。只有触发识别才会把截图或文字发送至用户配置的 API；API 服务商的数据处理规则由服务商决定。
- 屏幕内容和模型回答仅作为文本展示，不会执行其中的命令。答案仍需要用户核对。

## 从源码运行与打包

需要 Python 3.10+，建议 Python 3.13。

```powershell
# 首次运行：建立项目虚拟环境并安装 Pillow
.\run.ps1

# 或使用已经装有 Pillow 的 Python
python -m screenanswer

# 测试：使用本机模拟 API，不需要真实 Key
python -m unittest discover -v
python -m tests.smoke_windows

# 打包
python -m pip install -r requirements-build.txt
.\build.ps1
```

也可双击 `run.cmd` 从源码启动。`run.ps1` 首次运行需要联网下载依赖。`build.ps1` 使用当前 Python 环境；若在项目虚拟环境中安装了打包依赖，可用 `./build.ps1 -Python .venv/Scripts/python.exe`。

项目结构：`screenanswer/app.py` 为界面和任务调度，`core.py` 为 API、去重和配置，`windows.py` 与 `ocr.ps1` 为系统接口，`tests/` 为模拟 API 与 Windows 冒烟测试。

API 图片格式参考：[OpenAI 官方 Images and vision 文档](https://developers.openai.com/api/docs/guides/images-vision)。
