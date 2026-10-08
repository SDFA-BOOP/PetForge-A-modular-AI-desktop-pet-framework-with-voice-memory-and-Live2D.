use std::sync::OnceLock;

use anyhow::{anyhow, Result};
use ndarray::Array2;
use regex::Regex;

use super::phone_symbol::get_phone_symbol;

use jpreprocess::kind::JPreprocessDictionaryKind;
use jpreprocess::{DefaultTokenizer, JPreprocess, SystemDictionaryConfig};

static JP: OnceLock<JPreprocess<DefaultTokenizer>> = OnceLock::new();

fn jp() -> &'static JPreprocess<DefaultTokenizer> {
    JP.get_or_init(|| {
        let dict = SystemDictionaryConfig::Bundled(JPreprocessDictionaryKind::NaistJdic)
            .load()
            .expect("failed to load bundled naist-jdic dictionary");
        JPreprocess::with_dictionaries(dict, None)
    })
}

fn marks_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"[^A-Za-z\d\u{3005}\u{3040}-\u{30ff}\u{4e00}-\u{9fff}\u{ff11}-\u{ff19}\u{ff21}-\u{ff3a}\u{ff41}-\u{ff5a}\u{ff66}-\u{ff9d}]",
        )
        .unwrap()
    })
}

fn chars_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"[A-Za-z\d\u{3005}\u{3040}-\u{30ff}\u{4e00}-\u{9fff}\u{ff11}-\u{ff19}\u{ff21}-\u{ff3a}\u{ff41}-\u{ff5a}\u{ff66}-\u{ff9d}]",
        )
        .unwrap()
    })
}

fn post_replace(ph: &str) -> &str {
    match ph {
        "：" | "；" | "，" | "·" | "、" => ",",
        "。" => ".",
        "！" => "!",
        "？" => "?",
        "\n" => ".",
        "..." => "…",
        _ => ph,
    }
}

fn collapse_punctuation(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut prev: char = char::MAX;
    for ch in text.chars() {
        let is_p = matches!(ch, '!' | '?' | '…' | ',' | '.' | '-');
        let prev_p = matches!(prev, '!' | '?' | '…' | ',' | '.' | '-');
        if is_p && prev_p {
            continue;
        }
        out.push(ch);
        prev = ch;
    }
    out
}

fn extract_phoneme(label: &str) -> &str {
    let field = label.split('/').next().unwrap_or("");
    let dash = field.find('-');
    let plus = field.find('+');
    match (dash, plus) {
        (Some(d), Some(p)) if p > d + 1 => &field[d + 1..p],
        _ => "",
    }
}

/// 专有名词读音修正：避免 jpreprocess 把「勇太」按单字误读成「いさむ ふとし」。
/// 勇太 的规范读音是「ゆうた」（yuta / yūta）。
fn apply_name_readings(text: &str) -> String {
    text.replace("勇太", "ゆうた")
        .replace("ユウタ", "ゆうた")
}
/// Convert Japanese text to phoneme tokens, mirroring GPT-SoVITS `text.japanese.g2p`.
pub fn g2p(text: &str) -> Result<Vec<String>> {
    let text = text.to_lowercase();
    let text = apply_name_readings(&text);
    let text = collapse_punctuation(&text);

    let re_marks = marks_re();
    let re_chars = chars_re();

    let sentences: Vec<&str> = re_marks.split(&text).collect();
    let marks: Vec<&str> = re_marks.find_iter(&text).map(|m| m.as_str()).collect();

    let mut phones: Vec<String> = Vec::new();
    for (i, sentence) in sentences.iter().enumerate() {
        if re_chars.is_match(sentence) {
            let labels = jp()
                .extract_fullcontext(sentence)
                .map_err(|e| anyhow!("jpreprocess failed for '{}': {}", sentence, e))?;
            for lab in labels {
                let lab_s = lab.to_string();
                let ph = extract_phoneme(&lab_s);
                match ph {
                    "sil" => continue,
                    "pau" => phones.push("_".to_string()),
                    "" => continue,
                    other => phones.push(other.to_string()),
                }
            }
        }
        if i < marks.len() {
            let m = marks[i].replace(' ', "");
            if m.is_empty() {
                continue;
            }
            phones.push(post_replace(&m).to_string());
        }
    }

    Ok(phones)
}

/// Japanese text -> (chunk, phone_ids, zero BERT features).
/// BERT is not used for Japanese in GPT-SoVITS, so features are zeros (phones x 1024).
pub fn g2p_bert(text: &str) -> Result<Vec<(String, Vec<i64>, Array2<f32>)>> {
    let phones = g2p(text)?;
    let ids: Vec<i64> = phones.iter().map(|p| get_phone_symbol(p)).collect();
    let n = ids.len();
    if n == 0 {
        return Err(anyhow!("No phonemes generated for Japanese text: {}", text));
    }
    let bert = Array2::<f32>::zeros((n, 1024));
    Ok(vec![(text.to_string(), ids, bert)])
}

#[cfg(test)]
mod tests {
    use super::g2p;

    #[test]
    fn jp_g2p_basic() {
        assert_eq!(
            g2p("こんにちは。").unwrap(),
            vec!["k", "o", "N", "n", "i", "ch", "i", "w", "a", "."]
        );
        assert_eq!(g2p("待って").unwrap(), vec!["m", "a", "cl", "t", "e"]);
        assert_eq!(g2p("学校").unwrap(), vec!["g", "a", "cl", "k", "o", "o"]);
        assert_eq!(g2p("ほんと").unwrap(), vec!["h", "o", "N", "t", "o"]);
    }

    #[test]
    fn jp_g2p_yuuta() {
        // 「勇太」必须读成 ゆうた（yuta），不能按单字读成 いさむ ふとし。
        assert_eq!(g2p("勇太").unwrap(), vec!["y", "u", "u", "t", "a"]);
        assert_eq!(
            g2p("勇太くん").unwrap(),
            vec!["y", "u", "u", "t", "a", "k", "u", "N"]
        );
    }
}
