# characters — 角色素材说明

PetForge 是**角色无关**的框架，仓库不包含任何角色素材。角色资源放在各端自己的目录：

| 端 | 素材位置 | 说明 |
|----|----------|------|
| 电脑端 | `desktop/character/` | 立绘 PNG / Live2D 模型，见该目录 README |
| 安卓端 | `android/app/src/main/assets/web/model/` | Live2D 模型，见该目录 README |

## 换角色大概三步

1. 放入角色素材（Live2D `.model3.json` 或立绘 PNG）。
2. 在各自的 README / 配置里指向你的素材路径。
3. 替换人设提示词（`persona`）与 `config.json` 中的角色设定。

> 这些素材目录里的实际文件已被 `.gitignore` 忽略，你自己的角色资源不会误提交到仓库。
