#!/usr/bin/env python3
import subprocess
import datetime
import os
import multiprocessing
import json
from typing import Dict, List
import shutil
import sys
import logging
from enum import Enum
import yaml
from pathlib import Path


class Colors:
    """ANSI color codes"""

    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"


class CustomFormatter(logging.Formatter):
    """Custom formatter with colors"""

    format_str = "%(asctime)s [%(levelname)s] %(message)s"

    FORMATS = {
        logging.DEBUG: Colors.BLUE + format_str + Colors.RESET,
        logging.INFO: Colors.GREEN + format_str + Colors.RESET,
        logging.WARNING: Colors.YELLOW + format_str + Colors.RESET,
        logging.ERROR: Colors.RED + format_str + Colors.RESET,
        logging.CRITICAL: Colors.PURPLE + format_str + Colors.RESET,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def initialize_logger():
    logger = logging.getLogger("sysbench_tester")
    logger.setLevel(logging.INFO)

    # 避免重复添加 handler
    if not logger.hasHandlers():
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(CustomFormatter())
        logger.addHandler(console_handler)
    return logger


# 全局初始化 logger
logger = initialize_logger()


def load_config(config_path: str = "config.yaml") -> Dict:
    """Load test configuration from YAML file"""
    default_config = {
        "global": {"enabled_tests": ["cpu", "memory", "fileio"]},
        "cpu": {
            "enabled": True,
            "single_thread": {"enabled": True, "events": 0, "time": 30, "threads": 1},
            "multi_thread": {"enabled": True, "events": 0, "time": 30, "threads": "auto"},
        },
        "memory": {
            "enabled": True,
            "threads": 4,
            "time": 30,
            "block_size": "1K",
            "total_size": "100G",
        },
        "fileio": {
            "enabled": True,
            "file_total_size": "4G",
            "file_num": 4,
            "threads": 4,
            "time": 60,
            "modes": [
                {"name": "rndrw", "enabled": True},
                {"name": "seqrd", "enabled": True},
            ],
            "cleanup": True,
        },
    }

    config_path = Path(config_path)
    if not config_path.exists():
        logger.warning(f"Config file {config_path} not found, using default configuration")
        return default_config

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config
    except Exception as e:
        logger.error(f"Error loading config file: {str(e)}")
        logger.warning("Using default configuration")
        return default_config


def check_package_manager():
    """Check system package manager;use which to check"""
    if shutil.which("apt"):  # Debian/Ubuntu
        return "apt"
    elif shutil.which("yum"):  # CentOS/RHEL
        return "yum"
    elif shutil.which("dnf"):  # Fedora
        return "dnf"
    elif shutil.which("pacman"):  # Arch Linux
        return "pacman"
    return None


def install_package(package_name: str) -> bool:
    """Generic package installation function"""
    pkg_manager = check_package_manager()
    if not pkg_manager:
        logger.error("No supported package manager found (apt/yum/dnf/pacman)")
        return False

    logger.info(f"Installing {package_name} using {pkg_manager}...")
    try:
        if pkg_manager == "apt":
            # Update package list
            subprocess.run(["sudo", "apt", "update"], check=True)
            # Install package
            subprocess.run(["sudo", "apt", "install", "-y", package_name], check=True)
        elif pkg_manager in ["yum", "dnf"]:
            # For EPEL packages
            subprocess.run(["sudo", pkg_manager, "install", "-y", "epel-release"], check=True)
            # Install package
            subprocess.run(["sudo", pkg_manager, "install", "-y", package_name], check=True)
        elif pkg_manager == "pacman":
            # Update package database
            subprocess.run(["sudo", "pacman", "-Sy"], check=True)
            # Install package
            subprocess.run(["sudo", "pacman", "-S", "--noconfirm", package_name], check=True)

        return shutil.which(package_name) is not None

    except subprocess.CalledProcessError as e:
        logger.error(f"Error during {package_name} installation: {str(e)}")
        return False


def install_sysbench():
    """Install sysbench if not present"""
    logger.info("Checking sysbench...")

    # Check if sysbench is already installed
    if shutil.which("sysbench"):
        logger.info("sysbench is already installed")
        return True

    return install_package("sysbench")


def install_fastfetch():
    """Install fastfetch if not present"""
    logger.info("Checking fastfetch...")

    # Check if fastfetch is already installed
    if shutil.which("fastfetch"):
        logger.info("fastfetch is already installed")
        return True

    return install_package("fastfetch")


def get_system_info() -> Dict:
    """Collect system information using fastfetch"""
    if not install_fastfetch():
        logger.error("Failed to install fastfetch")
        return {}

    try:
        # 使用 --json 格式获取系统信息
        result = subprocess.run(["fastfetch", "--json"], capture_output=True, text=True, check=True)
        system_info = json.loads(result.stdout)
        logger.info("System information collected successfully")
        return system_info
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get system information: {str(e)}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse system information: {str(e)}")
        return {}


# TODO Add system information detection
# TODO Add network performance testing
class SysbenchTester:
    def __init__(self, config_path: str = "config.yaml"):
        # Load configuration
        self.config = load_config(config_path)

        # Check and install sysbench at program start
        if not install_sysbench():
            logger.critical("Unable to install sysbench, exiting program")
            sys.exit(1)

        self.results = {"system_info": {}, "benchmark_results": {}}
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.result_dir = f"results_{self.timestamp}"
        os.makedirs(self.result_dir, exist_ok=True)
        logger.info(f"Created results directory: {self.result_dir}")

        # Collect system information
        logger.info("Collecting system information...")
        self.results["system_info"] = get_system_info()

    def run_command(self, command: str, test_name: str) -> Dict:
        """Execute command and return results"""
        logger.info(f"Executing test: {test_name}")
        logger.debug(f"Command: {command}")

        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            logger.debug("Command executed successfully")
            return {
                "status": "success",
                "output": result.stdout,
                "command": command,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Command execution failed: {str(e)}")
            return {
                "status": "error",
                "output": e.stdout if e.stdout else str(e),
                "error": e.stderr if e.stderr else str(e),
                "command": command,
                "timestamp": datetime.datetime.now().isoformat(),
            }

    def run_cpu_tests(self):
        """Run CPU benchmark tests"""
        if not self.config["cpu"]["enabled"]:
            logger.info("CPU tests disabled in configuration")
            return

        # Single-thread CPU test
        if self.config["cpu"]["single_thread"]["enabled"]:
            cfg = self.config["cpu"]["single_thread"]
            self.results["benchmark_results"]["cpu_single_thread"] = self.run_command(
                f"sysbench cpu --events={cfg['events']} --time={cfg['time']} --threads={cfg['threads']} run",
                "CPU Single Thread Test",
            )

        # Multi-thread CPU test
        if self.config["cpu"]["multi_thread"]["enabled"]:
            cfg = self.config["cpu"]["multi_thread"]
            threads = multiprocessing.cpu_count() if cfg["threads"] == "auto" else cfg["threads"]
            self.results["benchmark_results"]["cpu_multi_thread"] = self.run_command(
                f"sysbench cpu --events={cfg['events']} --time={cfg['time']} --threads={threads} run",
                f"CPU Multi-Thread Test ({threads} threads)",
            )

    def run_memory_test(self):
        """Run memory benchmark test"""
        if not self.config["memory"]["enabled"]:
            logger.info("Memory tests disabled in configuration")
            return

        cfg = self.config["memory"]
        self.results["benchmark_results"]["memory"] = self.run_command(
            f"sysbench memory --threads={cfg['threads']} --time={cfg['time']} "
            f"--memory-block-size={cfg['block_size']} --memory-total-size={cfg['total_size']} run",
            "Memory Test",
        )

    def run_fileio_tests(self):
        """Run file I/O benchmark tests"""
        if not self.config["fileio"]["enabled"]:
            logger.info("File I/O tests disabled in configuration")
            return

        cfg = self.config["fileio"]

        # Prepare files
        self.results["benchmark_results"]["fileio_prepare"] = self.run_command(
            f"sysbench fileio --file-total-size={cfg['file_total_size']} --file-num={cfg['file_num']} prepare",
            "File I/O Preparation",
        )

        # Run enabled test modes
        for mode in cfg["modes"]:
            if mode["enabled"]:
                test_name = f"fileio_{mode['name']}"
                self.results["benchmark_results"][test_name] = self.run_command(
                    f"sysbench fileio --file-total-size={cfg['file_total_size']} "
                    f"--file-num={cfg['file_num']} --threads={cfg['threads']} "
                    f"--time={cfg['time']} --file-test-mode={mode['name']} run",
                    f"File I/O {mode['name'].upper()} Test",
                )

        # Cleanup files if configured
        if cfg["cleanup"]:
            self.results["benchmark_results"]["fileio_cleanup"] = self.run_command(
                f"sysbench fileio --file-total-size={cfg['file_total_size']} --file-num={cfg['file_num']} cleanup",
                "File I/O Cleanup",
            )

    def run_enabled_tests(self):
        """Run all enabled tests according to configuration"""
        enabled_tests = self.config["global"]["enabled_tests"]

        for test in enabled_tests:
            if test == "cpu" and self.config["cpu"]["enabled"]:
                self.run_cpu_tests()
            elif test == "memory" and self.config["memory"]["enabled"]:
                self.run_memory_test()
            elif test == "fileio" and self.config["fileio"]["enabled"]:
                self.run_fileio_tests()

    def _parse_cpu_result(self, output: str) -> Dict:
        """Parse CPU test results"""
        lines = output.split("\n")
        result = {"threads": None, "time": None, "events_per_second": None}

        for line in lines:
            if "Number of threads:" in line:
                result["threads"] = line.split(":")[1].strip()
            elif "total time:" in line:
                result["time"] = line.split(":")[1].strip()
            elif "events per second:" in line:
                result["events_per_second"] = line.split(":")[1].strip()

        return result

    def _parse_memory_result(self, output: str) -> Dict:
        """Parse memory test results"""
        lines = output.split("\n")
        result = {"block_size": None, "transfer_speed": None, "total_time": None, "latency_sum": None}

        for line in lines:
            if "block size:" in line:
                result["block_size"] = line.split(":")[1].strip()
            elif "MiB transferred" in line:
                result["transfer_speed"] = line.split("(")[1].split(")")[0]
            elif "total time:" in line:
                result["total_time"] = line.split(":")[1].strip()
            elif "sum:" in line and result["latency_sum"] is None:
                result["latency_sum"] = line.split(":")[1].strip()

        return result

    def _parse_fileio_result(self, output: str) -> Dict:
        """Parse file I/O test results"""
        lines = output.split("\n")
        result = {"read_throughput": None, "write_throughput": None, "latency_sum": None}

        for line in lines:
            if "read, MiB/s:" in line:
                result["read_throughput"] = line.split(":")[1].strip()
            elif "written, MiB/s:" in line:
                result["write_throughput"] = line.split(":")[1].strip()
            elif "sum:" in line and result["latency_sum"] is None:
                result["latency_sum"] = line.split(":")[1].strip()

        return result

    def save_results(self):
        """Save test results"""
        # Save raw JSON results
        json_path = os.path.join(self.result_dir, "raw_results.json")
        with open(json_path, "w") as f:
            json.dump(self.results, f, indent=4)
        logger.debug(f"Raw results saved to: {json_path}")

        # Generate simplified human-readable report
        report_path = os.path.join(self.result_dir, "report.txt")
        with open(report_path, "w") as f:
            f.write(f"Sysbench Performance Test Report (Simplified)\n")
            f.write(f"Test Time: {self.timestamp}\n")
            f.write("=" * 50 + "\n\n")

            # System Information
            f.write("System Information\n")
            f.write("-" * 30 + "\n")
            if self.results["system_info"]:
                for key, value in self.results["system_info"].items():
                    f.write(f"{key}: {value}\n")
            else:
                f.write("System information not available\n")
            f.write("\n")

            # CPU test results
            for test_name in ["cpu_single_thread", "cpu_multi_thread"]:
                if (
                    test_name in self.results["benchmark_results"]
                    and self.results["benchmark_results"][test_name]["status"] == "success"
                ):
                    result = self._parse_cpu_result(self.results["benchmark_results"][test_name]["output"])
                    f.write(f"\nCPU Test - {'Single Thread' if 'single' in test_name else 'Multi Thread'}\n")
                    f.write("-" * 30 + "\n")
                    f.write(f"Test Threads: {result['threads']}\n")
                    f.write(f"Test Duration: {result['time']}\n")
                    f.write(f"CPU Speed: {result['events_per_second']} events/sec\n")

            # Memory test results
            if (
                "memory" in self.results["benchmark_results"]
                and self.results["benchmark_results"]["memory"]["status"] == "success"
            ):
                result = self._parse_memory_result(self.results["benchmark_results"]["memory"]["output"])
                f.write(f"\nMemory Test\n")
                f.write("-" * 30 + "\n")
                f.write(f"Test Options: Block Size {result['block_size']}\n")
                f.write(f"Transfer Speed: {result['transfer_speed']}\n")
                f.write(f"Total Latency: {result['latency_sum']}\n")

            # File I/O test results
            for test_name in ["fileio_rndrw", "fileio_seqrd"]:
                if (
                    test_name in self.results["benchmark_results"]
                    and self.results["benchmark_results"][test_name]["status"] == "success"
                ):
                    result = self._parse_fileio_result(
                        self.results["benchmark_results"][test_name]["output"]
                    )
                    f.write(
                        f"\nDisk Test - {'Random Read/Write' if 'rndrw' in test_name else 'Sequential Read'}\n"
                    )
                    f.write("-" * 30 + "\n")
                    f.write(f"Read Speed: {result['read_throughput']} MiB/s\n")
                    if result["write_throughput"]:
                        f.write(f"Write Speed: {result['write_throughput']} MiB/s\n")
                    f.write(f"Total Latency: {result['latency_sum']} ms\n")

        logger.info("Test completed!")
        logger.info(f"Results saved to: {self.result_dir}/")
        logger.info(f"- Raw data: {json_path}")
        logger.info(f"- Summary report: {report_path}")


def main():
    # Accept optional config file path from command line
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"

    tester = SysbenchTester(config_path)
    logger.info("Starting Sysbench Performance Test...")
    tester.run_enabled_tests()
    tester.save_results()


if __name__ == "__main__":
    main()
