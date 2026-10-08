# PetForge 使用说明书

> 通用 AI 桌宠框架；文中示例角色为「小鸟游六花」，可替换为任意角色。

> 对应源码目录：`E:\PetForge`

---

## 1. 项目简介

本项目是一个可复用的 AI 桌宠框架，三端：

| 端 | 位置 | 技术 |
|----|------|------|
| 电脑端 | `desktop/` | Python + Tkinter + Live2D(py) |
| 安卓端 | `android/` | Java + WebView（PIXI.js + Cubism SDK） |
| 语音引擎 | `engine/` | Rust + ONNX Runtime（GPT-SoVITS 本地推理） |

各端运行/构建步骤见 `docs/BUILD.md`。

---

## 2. 核心概念：Live2D 参数绑定

Live2D 模型靠“参数 ID + 数值”来驱动表情与动作。本项目把「代码里的语义动作」和「模型参数 ID」解耦：

- 代码只写语义名（如 `mouth`、`angle_x`）。
- 实际模型参数 ID 在绑定表中集中配置。
- **换模型 / 改参数，只改绑定表，不用改渲染逻辑。**

### 2.1 默认绑定表（示例「T」模型）

| 语义名 | 默认参数 ID | 作用 | 取值范围示例 |
|--------|-------------|------|--------------|
| `mouth` | `Param4` | 嘴部开合 | -30（闭）~ 30（张） |
| `hair_front` | `ParamHairFront` | 前发 / 呆毛 | 约 -1 ~ 1 |
| `body_sway_1` | `Param3` | 身体摆动 1 | 约 -2.6 ~ 2.6 |
| `body_sway_2` | `Param` | 身体摆动 2 | 约 -1.2 ~ 1.2 |
| `body_sway_3` | `Param2` | 身体摆动 3 | 约 -1.2 ~ 1.2 |
| `angle_x` | `ParamAngleX` | 头部左右（追鼠标/人脸） | -22 ~ 22 |
| `angle_y` | `ParamAngleY` | 头部上下 | -16 ~ 16 |
| `angle_z` | `ParamAngleZ` | 头部倾斜 | 约 -2.6 ~ 2.6 |

> 电脑端在 `desktop/petforge/character/live2d.py` 的 `PARAMETER_MAP`；
> 安卓端在 `android/app/src/main/assets/web/app.js` 的 `setParameter(...)` 调用处。

---

## 3. 如何更改绑定变量

### 3.1 电脑端（推荐）

编辑 `desktop/petforge/character/live2d.py` 顶部的 `PARAMETER_MAP`：

```python
PARAMETER_MAP = {
    "mouth": "Param4",              # 改成你自己的嘴部参数 ID
    "hair_front": "ParamHairFront",
    "body_sway_1": "Param3",
    "body_sway_2": "Param",
    "body_sway_3": "Param2",
    "angle_x": "ParamAngleX",
    "angle_y": "ParamAngleY",
    "angle_z": "ParamAngleZ",
}
```

例如换成官方 Cubism 示例模型的嘴部参数：

```python
PARAMETER_MAP["mouth"] = "ParamMouthOpenY"
```

保存后重启桌宠即可生效。

### 3.2 安卓端

编辑 `android/app/src/main/assets/web/app.js`，找到 `setParameter(...)` 调用（约 1531~1567 行），把参数名替换为你的模型参数 ID：

```js
// 嘴部（原 Param4）
setParameter('ParamMouthOpenY', -1 + 2 * mouth);   // 改成你的模型
// 头部跟随
setParameter('ParamAngleX', faceX * 36 * amplitude * followGain);
setParameter('ParamAngleY', -faceY * 28 * amplitude * followGain);
setParameter('ParamAngleZ', faceX * 5 * amplitude * followGain);
// 待机摆动
setParameter('ParamHairFront', 0.32 * amplitude * idleGain * Math.sin(phase * Math.PI * 2 / 3.8));
setParameter('Param3', 2.4 * amplitude * idleGain * Math.sin(phase * Math.PI * 2 / 5.4));
setParameter('Param', 1.0 * amplitude * idleGain * Math.sin(phase * Math.PI * 2 / 5.4 + 0.5));
setParameter('Param2', -1.0 * amplitude * idleGain * Math.sin(phase * Math.PI * 2 / 5.4 + 0.5));
```

### 3.3 如何知道模型的参数 ID？

- 用 Live2D Cubism Editor 打开 `.cmo3`，在「参数」面板查看参数 ID。
- 或临时打印：电脑端在 `Live2DWidget._ensure_model()` 后调用 `print(self.param_ids)`，即可看到模型全部参数 ID。
- 安卓端可在 `app.js` 里 `console.log(coreModel._model.getParameterIds())` 查看。

---

## 4. 自定义动作扩展接口（绑定更多动作）

### 4.1 电脑端 `register_action`

`desktop/petforge/character/live2d.py` 提供了 `register_action()`：

```python
from petforge.character.live2d import register_action
```

回调签名：`func(widget, t, dt, now)`

- `widget`：`Live2DWidget`，可用 `widget.bind("语义名", 值)` 设置参数
- `t`：距启动秒数
- `dt`：本帧间隔秒
- `now`：`time.monotonic()`

**示例 1：让某个参数跟着呼吸起伏**

在 `main.py` 的 `run()` 之前、或任意会执行一次的地方注册：

```python
import math
from petforge.character.live2d import register_action

def breath_extra(widget, t, dt, now):
    # 注意：参数 ID 需先加入 PARAMETER_MAP，或直接用 bind("实际参数ID", ...)
    widget.bind("ParamBreath", 0.5 + 0.5 * math.sin(t * math.tau / 4.0))

register_action(breath_extra)
```

**示例 2：周期性甩呆毛**

```python
def periodic_ahoge(widget, t, dt, now):
    if int(t) % 6 < 2:  # 每 6 秒甩 2 秒
        widget.bind("hair_front", 0.8 * math.sin(t * math.tau * 6))

register_action(periodic_ahoge)
```

**示例 3：用装饰器写法**

```python
@register_action
def custom_idle(widget, t, dt, now):
    widget.bind("body_sway_1", 3.0 * math.sin(t * math.tau / 5.0))
```

> 注册的回调每帧调用，已内置异常保护（单个回调出错不影响渲染）。所有 `register_action` 注册的动作会和内置动作叠加执行。

### 4.2 安卓端自定义动作

安卓端直接在 `app.js` 的动画循环里（约 1531 行附近）追加 `setParameter(...)` 调用即可；也可封装成数组逐个执行，便于扩展。

---

## 5. 让 AI 返回动作 / 表情（用户可自定义）

AI 可以在回复**末尾**附带一个标签来触发表情或动作，标签不会显示给用户，也不会被配音朗读：

- `[表情:angry]` —— 直接切换表情
- `[动作:wave]` —— 触发自定义动作
- 英文等价：`[emotion:angry]`、`[action:wave]`

### 5.1 内置表情 / 动作

- 表情：`neutral / happy / excited / shy / sad / angry / surprised / thinking`
- 动作：`idle / tap / shake / ahoge`（`ahoge` = 甩呆毛）

### 5.2 用户自定义动作

在桌宠根目录新建 `user_actions.py`（示例见 `desktop/user_actions.py`）：

```python
from petforge.actions import register_action

@register_action("wave")
def wave(char, direction=1):
    char.set_action("wave", direction)

@register_action("blush")
def blush(char, direction=1):
    char.set_emotion("shy")
```

启动时会自动加载该文件。动作函数签名 `func(char, direction=1)`：

- `char`：当前角色模型
- `direction`：可选方向（+1 / -1）

若角色是 Live2D，还可以直接绑参数：

```python
@register_action("nod")
def nod(char, direction=1):
    widget = getattr(char, "widget", None)
    if widget is not None:
        widget.bind("angle_y", -10.0)   # 语义名见 live2d.PARAMETER_MAP
```

### 5.3 实现说明

- 解析逻辑在 `desktop/petforge/actions.py`（`parse_action` / `dispatch` / `register_action`）。
- 标签必须位于回复末尾；标签文本会从聊天窗、记忆、配音里全部剥离。
- 提示词里的动作说明（`persona.ACTION_HINT`）会**自动附加到系统提示词**，即使你使用了自定义人设（`persona_custom`）也会生效。

---

## 6. 常见问题

- **换了模型没反应**：检查参数 ID 是否写对；电脑端打印 `self.param_ids`，安卓端打印 `getParameterIds()`。
- **参数值范围不对**：Live2D 参数默认范围是 0~1（或模型自定义范围），先看模型里该参数的默认/最小/最大值，再调整上面的系数。
- **动作没生效**：确认 `register_action` 在模型创建前调用，且回调内部 `bind` 的语义名已存在于 `PARAMETER_MAP`。
