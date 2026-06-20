# 🚦 agent 红绿灯监控

一个轻量级的桌面红绿灯监控器，用于追踪本机多个 **Claude Code** / **Codex** CLI 会话的运行状态。

![concept](https://img.shields.io/badge/status-running-FDD835) ![concept](https://img.shields.io/badge/status-success-66BB6A) ![concept](https://img.shields.io/badge/status-failed-EF5350)

![示例](https://i.meee.com.tw/IU80U2P.png)

## 这是什么

在多窗口并行 "vibe coding" 时，你常常开了 3、4 个 agent 各自跑任务：
- 一个在写代码（RUNNING）
- 一个跑完了（SUCCESS）
- 一个挂了（FAILED）
- 还有一个进程已经死掉（DEAD）

挨个窗口切去看太累。`agent 红绿灯监控` 在桌面上挂一个置顶的小灯箱面板，每开一个 agent 会话，就给它点上一张三色灯卡片，红/黄/绿一目了然。

## 工作原理

```
┌────────────────────────┐          ┌──────────────────────┐
│  agent 进程 (claude/   │  UDP     │  agent 红绿灯监控    │
│  codex) 调用           │ ───────► │  桌面 GUI            │
│  python main.py run X  │  127.0.1 │  - 三色灯卡片        │
└────────────────────────┘   :18888 │  - 进程存活检测      │
                                    │  - 拖拽 / 双击退出   │
                                    └──────────────────────┘
```

- **发送端**：`python main.py <action> <name>` —— 一行命令发一个 UDP 包给桌面端，包里带上发送进程沿父进程链找到的 agent PID。`action` 除了状态灯（`run`/`success`/`error`）外，还支持 `hide` / `show` / `quit` 控制面板本身。
- **接收端**：`python main.py` —— 启动一个置顶无边的 tk 窗口，监听 `127.0.0.1:18888`，每收到一个包就更新对应卡片的状态灯。隐藏后进程仍在后台运行，可随时用 `show` 唤回。
- **存活检测**：每 3 秒检查一次卡片绑定的 PID 是否还在，进程没了就把卡片标成 DEAD。

## 安装

只需要 Python 3 自带的 `tkinter`，无第三方依赖。

**macOS**（默认自带）：
```bash
python3 main.py
```

**Linux** 可能需要装一下：
```bash
sudo apt install python3-tk
```

## 使用

### 1. 启动桌面端（一次就够）

```bash
python3 main.py
# 🚦 红绿灯界面已启动，请将此窗口留在后台。
```

窗口置顶、无边框，**拖拽移动**，**双击或右键退出**。
不想看到面板时，发 `hide` 即可完全隐藏（含任务栏），进程继续在后台运行；用 `show` 恢复。

### 2. 在 agent 会话里发信号

```bash
python3 main.py run      my_project     # 黄灯：开始运行
python3 main.py success  my_project     # 绿灯：成功
python3 main.py error    my_project     # 红灯：失败
python3 main.py run,success my_project  # 多灯同时亮

# —— 控制面板本身 ——
python3 main.py hide     _              # 完全隐藏窗口（进程继续在后台跑）
python3 main.py show     _              # 恢复显示
```

第二个参数 `my_project` 是卡片名，相同名字会复用同一张卡片。
`hide` / `show` 不关心卡片名，随便传一个占位参数（如 `_`）即可。

### 3. 接入 Claude Code / Codex

把上面的发送命令塞进 agent 的 hook 里，让它在状态切换时自动发信号。

**Claude Code**（`~/.claude/settings.json`）：
```json
{
  "SessionStart": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "/usr/bin/python3 /path/to/agent-traffic-light/main.py success $(basename $PWD)"
        }
      ]
    }
  ],
  "UserPromptSubmit": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "/usr/bin/python3 /path/to/agent-traffic-light/main.py run $(basename $PWD)"
        }
      ]
    }
  ],
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "/usr/bin/python3 /path/to/agent-traffic-light/main.py success $(basename $PWD)"
        }
      ]
    }
  ]
}
```

卡片名用 `$(basename $PWD)`（当前项目目录名），这样每个项目的卡片自动区分。把 `/path/to/agent-traffic-light/main.py` 换成你本机的实际路径。

**Codex**（`~/.codex/config.toml`）：

请先确认 `config.toml` 中已经把 hook 功能打开（设为 `true`），否则下面配置的事件不会触发：

```toml
[features]
hooks = true
```

然后在 `~/.codex/hooks.json`（或对应的 hook 配置文件）里配置生命周期事件：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "/usr/bin/python3 /Users/tina/Code/agent-traffic-light/main.py success $(basename $PWD)"}]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "/usr/bin/python3 /Users/tina/Code/agent-traffic-light/main.py run $(basename $PWD)"}]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "/usr/bin/python3 /Users/tina/Code/agent-traffic-light/main.py success $(basename $PWD)"}]
      }
    ]
  }
}
```

`main.py` 在识别父进程时同时匹配 `claude` 和 `codex` 两个关键字，所以存活检测对两者都生效。把 `/Users/tina/Code/agent-traffic-light/main.py` 换成你本机的实际路径。

## 状态颜色

| 状态 | 灯色 | 含义 |
|------|------|------|
| `run` | 🟡 黄 | 运行中 |
| `success` | 🟢 绿 | 成功 |
| `error` | 🔴 红 | 失败 |
| (无) | ⚫ 灰 | IDLE |
| 进程退出 | - | 卡片自动销毁 |

## 配置

所有可调参数都在 `main.py` 顶部：

```python
PORT = 18888              # UDP 端口
CHECK_INTERVAL = 3000     # 存活检测间隔（毫秒）
AGENTS = {"claude": ..., "codex": ...}  # 父进程识别关键字
```

## FAQ

**Q: 端口被占了怎么办？**
A: 改 `PORT`，发送端和接收端同步即可。

**Q: macOS 上找不到 tkinter？**
A: 用 `python3` 而不是系统自带的 `python`，或者用 brew 装的 python。

**Q: 能不能加更多 agent？**
A: 在 `AGENTS` 字典里加一项即可，例如 `"aider": "aider"`。

## License

MIT

## 联系

有问题欢迎邮件联系：[1105504520@qq.com](mailto:1105504520@qq.com)
