# Linux 性能测试工具

这是一个基于 sysbench 和 fastfetch 的 Linux 系统性能测试工具，可以测试 CPU、内存、磁盘I/O 和网络性能。

## 特性

- 自动安装依赖软件包（sysbench、fastfetch）
- 支持多种 Linux 发行版（基于apt、yum、dnf、pacman包管理器）
- 测试项目可配置（CPU单/多线程、内存、磁盘I/O、网络）
- 测试结果自动保存和可视化
- 系统信息收集
- YAML 配置格式

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/Linux_performance_test.git
cd Linux_performance_test
```

2. 安装依赖：
```bash
pip install pyyaml requests
# 可视化功能需要matplotlib
pip install matplotlib
```

## 使用方法

1. 编辑配置文件 `config.yaml`（或使用默认配置）
2. 执行测试：
```bash
python sysbench_test.py
# 或指定配置文件路径
python sysbench_test.py custom_config.yaml
```

3. 查看测试结果：
   - 原始数据：`results_YYYYMMDD_HHMMSS/raw_results.json`
   - 摘要报告：`results_YYYYMMDD_HHMMSS/report.txt`
   - 可视化图表：`results_YYYYMMDD_HHMMSS/visualizations/`

## 配置说明

配置文件为YAML格式，包含以下主要部分：

- `global`: 全局设置，包括启用的测试项目
- `cpu`: CPU测试配置（单线程和多线程）
- `memory`: 内存测试配置
- `fileio`: 文件I/O测试配置
- `network`: 网络测试配置（需要iperf3服务器）

详细配置示例见 `config.yaml`。

## 网络测试

要使用网络测试功能，需要：

1. 在配置文件中启用网络测试：`network.enabled: true`
2. 设置iperf3服务器IP地址：`network.server_ip: "服务器IP"`
3. 在服务器端运行：`iperf3 -s`

## 系统要求

- Python 3.6+
- 支持的Linux发行版：
  - Debian/Ubuntu系列 (apt)
  - RHEL/CentOS/Fedora系列 (yum/dnf)
  - Arch Linux系列 (pacman)
- 具有sudo权限的用户账号

## 许可证

[MIT License](LICENSE)
