package com.example.gpt_sovits_demo;

public final class MainActivity {
    static {
        System.loadLibrary("onnxruntime");
        System.loadLibrary("gpt_sovits_demo_jni");
    }

    public static native long initModel(String g2pW, String vits, String ssl,
                                        String t2sEncoder, String t2sFsdec, String t2sSdec,
                                        String bert, long numLayers);

    public static native boolean processReferenceSync(long handle, String refAudio, String refText, int lang);

    public static native float[] runInferenceSync(long handle, String text, int lang);

    public static native void freeModel(long handle);

    public static native void setProgressCallback(long handle, Object callback);
}
