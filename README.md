# Audio → MP3 Converter

批量将音频文件（M4A / AAC / FLAC / WAV / OGG / WMA / OPUS）转换为 MP3，支持图形界面操作、多文件并行转换、实时进度显示。

> Batch audio-to-MP3 converter with GUI, parallel processing, and real-time progress.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey) ![License](https://img.shields.io/badge/License-MIT-green)

---

## 功能 Features

- ☑ 勾选框选择要转换的文件，支持单选 / 全选
- ⚡ 多进程并行转换，速度随 CPU 核数线性提升
- 📊 每个文件实时显示转换进度百分比
- 📁 源目录 / 目标目录 / ffmpeg 路径均可自由配置
- 💾 配置自动保存，下次打开无需重新设置
- 🔍 首次运行自动检测 ffmpeg，未找到时提供下载引导

---

## 环境要求 Requirements

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | [下载](https://www.python.org/downloads/) |
| ffmpeg | 任意 | 见下方安装说明 |

> 所有 Python 依赖均为标准库，无需 `pip install`。

---

## 安装 Installation

### 1. 安装 Python

前往 https://www.python.org/downloads/ 下载安装。

安装时勾选 **"Add Python to PATH"**。

### 2. 安装 ffmpeg

**方式 A — 自动下载（推荐，首次运行时引导）**

直接运行程序，若检测不到 ffmpeg，会弹出提示并提供一键下载。

**方式 B — 手动安装（Windows）**

```powershell
winget install Gyan.FFmpeg
```

或前往 https://ffmpeg.org/download.html 下载，解压后在程序界面的 **ffmpeg** 一栏手动选择 `ffmpeg.exe` 路径。

### 3. 下载本工具

```bash
git clone https://github.com/Tofuzhu/audio-mp3-converter.git
cd audio-mp3-converter
```

---

## 使用方法 Usage

```bash
python mp3converter.py
```

1. **Source dir** — 选择包含音频文件的目录
2. **Dest dir** — 选择输出 MP3 的目标目录
3. **ffmpeg** — 首次使用若未自动检测到，点 Browse 手动指定 `ffmpeg.exe`
4. 在文件列表中点击行勾选要转换的文件（不勾则转换全部）
5. 选择码率和并行数，点 **▶ Start**

> 点击 **⚙ Save cfg** 保存当前配置，下次打开自动恢复。

---

## ffmpeg 路径说明

程序按以下顺序自动查找 ffmpeg：

1. 系统 `PATH`（winget 安装后通常在此）
2. `C:\ffmpeg\bin\ffmpeg.exe`
3. `D:\ffmpeg\bin\ffmpeg.exe`
4. 程序同目录下的 `ffmpeg\bin\ffmpeg.exe`
5. 上次保存的配置路径

若均未找到，启动时会弹出引导对话框。

也可以将 `ffmpeg.exe` 所在的 `bin` 目录解压到程序同级目录：

```
audio-mp3-converter/
├── mp3converter.py
├── ffmpeg/
│   └── bin/
│       └── ffmpeg.exe   ← 放这里即可自动识别
```

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `mp3converter.py` | 主程序（GUI） |
| `convert-to-mp3.ps1` | 命令行版本（PowerShell） |
| `mp3converter_config.json` | 用户配置（自动生成，无需手动编辑） |

---

## License

MIT
