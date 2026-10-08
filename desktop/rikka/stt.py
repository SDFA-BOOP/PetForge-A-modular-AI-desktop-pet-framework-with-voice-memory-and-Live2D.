"""语音输入：基于 speech_recognition + Google Web 识别（未安装时优雅降级，不阻止程序启动）。"""
from __future__ import annotations

try:
    import speech_recognition as sr
    _SR_OK = True
except ImportError:
    sr = None
    _SR_OK = False


class STTError(Exception):
    """语音识别异常（含未听清、网络错误、依赖缺失等）。"""


def _check_dep():
    if not _SR_OK:
        raise STTError("未安装语音识别库 SpeechRecognition，请先运行 setup.bat 安装依赖。")


def listen(language: str = "zh-CN", timeout: int = 6, phrase_time_limit: int = 15) -> str:
    """录音并识别为文本，返回识别结果；失败抛 STTError。"""
    _check_dep()
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    except Exception as e:
        raise STTError(f"无法访问麦克风: {e}")

    try:
        return recognizer.recognize_google(audio, language=language)
    except sr.UnknownValueError:
        raise STTError("没听清，请再说一次～")
    except sr.RequestError as e:
        raise STTError(f"语音服务请求失败（需联网）: {e}")
    except Exception as e:
        raise STTError(f"识别失败: {e}")
