"""角色模型：可插拔的人物渲染接口与实现。"""
from .base import CharacterModel, create_model, available_models, register_model  # noqa: F401

# 导入实现以触发注册
from . import image  # noqa: F401
from . import layered  # noqa: F401
from . import live2d  # noqa: F401
from . import sprite  # noqa: F401

