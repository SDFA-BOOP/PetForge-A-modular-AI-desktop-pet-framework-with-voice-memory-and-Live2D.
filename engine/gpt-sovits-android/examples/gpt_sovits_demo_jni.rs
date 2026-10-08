use gpt_sovits_onnx_rs::*;
use std::path::{Path, PathBuf};

use jni::objects::{GlobalRef, JClass, JObject, JString, JValue};
use jni::sys::{jboolean, jfloatArray, jint, jlong};
use jni::JNIEnv;
use log::LevelFilter;

const JNI_TRUE: jboolean = 1;
const JNI_FALSE: jboolean = 0;

fn init_logging() {
    android_logger::init_once(
        android_logger::Config::default()
            .with_max_level(LevelFilter::Info)
            .with_tag("rust.gpt_sovits"),
    );
}

fn lang_from_int(lang: jint) -> LangId {
    match lang {
        1 => LangId::Ja,
        2 => LangId::AutoYue,
        _ => LangId::Auto,
    }
}

fn opt_path(s: String) -> Option<PathBuf> {
    if s.trim().is_empty() {
        None
    } else {
        Some(PathBuf::from(s))
    }
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_example_gpt_1sovits_1demo_MainActivity_initModel(
    mut env: JNIEnv,
    _class: JClass,
    g2p_w_path: JString,
    vits_path: JString,
    ssl_path: JString,
    t2s_encoder_path: JString,
    t2s_fs_decoder_path: JString,
    t2s_s_decoder_path: JString,
    bert_path: JString,
    max_length: jlong,
) -> jlong {
    init_logging();
    let mut get = |s: JString| -> String {
        env.get_string(&s).map(|s| s.into()).unwrap_or_default()
    };
    let g2p_w = get(g2p_w_path);
    let vits = get(vits_path);
    let ssl = get(ssl_path);
    let t2s_encoder = get(t2s_encoder_path);
    let t2s_fs_decoder = get(t2s_fs_decoder_path);
    let t2s_s_decoder = get(t2s_s_decoder_path);
    let bert = get(bert_path);

    let max_length_usize = usize::try_from(max_length).unwrap_or(512);

    match TTSModel::new(
        Path::new(&vits),
        Path::new(&ssl),
        Path::new(&t2s_encoder),
        Path::new(&t2s_fs_decoder),
        Path::new(&t2s_s_decoder),
        max_length_usize,
        opt_path(bert).as_deref(),
        opt_path(g2p_w).as_deref(),
        None,
    ) {
        Ok(model) => Box::into_raw(Box::new(model)) as jlong,
        Err(e) => {
            let _ = env.throw_new("java/lang/RuntimeException", format!("Failed to initialize model: {}", e));
            0
        }
    }
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_example_gpt_1sovits_1demo_MainActivity_processReferenceSync(
    mut env: JNIEnv,
    _class: JClass,
    model_handle: jlong,
    ref_audio_path: JString,
    ref_text: JString,
    lang: jint,
) -> jboolean {
    let model: &mut TTSModel = unsafe { &mut *(model_handle as *mut TTSModel) };
    let ref_audio: String = env.get_string(&ref_audio_path).map(|s| s.into()).unwrap_or_default();
    let ref_text: String = env.get_string(&ref_text).map(|s| s.into()).unwrap_or_default();

    match model.process_reference_sync(Path::new(&ref_audio), &ref_text, lang_from_int(lang)) {
        Ok(_) => JNI_TRUE,
        Err(e) => {
            let _ = env.throw_new("java/lang/RuntimeException", format!("Failed to process reference: {}", e));
            JNI_FALSE
        }
    }
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_example_gpt_1sovits_1demo_MainActivity_runInferenceSync(
    mut env: JNIEnv,
    _class: JClass,
    model_handle: jlong,
    text: JString,
    lang: jint,
) -> jfloatArray {
    let model: &mut TTSModel = unsafe { &mut *(model_handle as *mut TTSModel) };
    let text: String = env.get_string(&text).map(|s| s.into()).unwrap_or_default();

    match model.synthesize_sync(
        &text,
        SamplingParamsBuilder::new().top_k(5).top_p(1.0).build(),
        lang_from_int(lang),
    ) {
        Ok((_, samples_vec)) => {
            let float_array = match env.new_float_array(samples_vec.len() as i32) {
                Ok(arr) => arr,
                Err(e) => {
                    let _ = env.throw_new("java/lang/RuntimeException", format!("Couldn't create float array: {}", e));
                    return std::ptr::null_mut();
                }
            };
            match env.set_float_array_region(&float_array, 0, &samples_vec) {
                Ok(_) => float_array.into_raw(),
                Err(e) => {
                    let _ = env.throw_new("java/lang/RuntimeException", format!("Couldn't set float array: {}", e));
                    std::ptr::null_mut()
                }
            }
        }
        Err(e) => {
            let _ = env.throw_new("java/lang/RuntimeException", format!("Failed to run inference: {}", e));
            std::ptr::null_mut()
        }
    }
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_example_gpt_1sovits_1demo_MainActivity_freeModel(
    _env: JNIEnv,
    _class: JClass,
    model_handle: jlong,
) {
    if model_handle != 0 {
        unsafe { drop(Box::from_raw(model_handle as *mut TTSModel)) };
    }
}




#[unsafe(no_mangle)]
pub extern "system" fn Java_com_example_gpt_1sovits_1demo_MainActivity_setProgressCallback(
    mut env: JNIEnv,
    _class: JClass,
    model_handle: jlong,
    callback: JObject,
) {
    if model_handle == 0 {
        return;
    }
    let model: &mut TTSModel = unsafe { &mut *(model_handle as *mut TTSModel) };
    let Ok(vm) = env.get_java_vm() else { return };
    let Ok(global) = env.new_global_ref(callback) else { return };
    let cb: std::sync::Arc<dyn Fn(u32) + Send + Sync> = std::sync::Arc::new(move |p: u32| {
        if let Ok(mut env) = vm.attach_current_thread() {
            let _ = env.call_method(&global, "onProgress", "(I)V", &[JValue::Int(p as i32)]);
        }
    });
    model.set_progress_callback(Some(cb));
}