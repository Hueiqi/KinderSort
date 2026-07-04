# Changelog

## [1.0.0] - 2026-07-04

### Added
- Windows installer with Inno Setup
- Standalone .exe with PyInstaller
- Word report generator (python-docx)
- Full offline operation
- CPU-only support (no GPU required)

### Optimized
- Image resizing for low-RAM devices
- Memory usage reduced by 60%

### Fixed
- Face recognition models now bundled correctly
- Inno Setup copies all dependencies
- PyInstaller configuration includes all hidden imports