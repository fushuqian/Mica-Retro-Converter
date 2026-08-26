fn main() {
    // 注意：项目路径含空格会导致 MinGW windres (tauri-winres) 预处理失败。
    // 若遇到 windres "No such file or directory" 错误，请把项目移动到不含空格的目录
    //（如 C:\workspace\win98-asf-converter）再构建。
    tauri_build::build()
}
