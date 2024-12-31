#!/usr/bin/env python3
import subprocess
import datetime
import os
import multiprocessing
import json
from typing import Dict, List


# TODO 添加sysbench安装检测
# TODO 添加系统信息检测、
# TODO 添加网络性能检测
class SysbenchTester:
    def __init__(self):
        self.results = {}
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.result_dir = f"results_{self.timestamp}"
        os.makedirs(self.result_dir, exist_ok=True)

    def run_command(self, command: str, test_name: str) -> Dict:
        """执行命令并返回结果"""
        print(f"\n执行测试: {test_name}")
        print(f"命令: {command}")

        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            return {
                "status": "success",
                "output": result.stdout,
                "command": command,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        except subprocess.CalledProcessError as e:
            return {
                "status": "error",
                "output": e.stdout if e.stdout else str(e),
                "error": e.stderr if e.stderr else str(e),
                "command": command,
                "timestamp": datetime.datetime.now().isoformat(),
            }

    def run_cpu_tests(self):
        """运行CPU测试"""
        # 单线程CPU测试
        self.results["cpu_single_thread"] = self.run_command(
            "sysbench cpu --events=0 --time=30 --threads=1 run", "CPU单线程测试"
        )

        # 多线程CPU测试
        cpu_count = multiprocessing.cpu_count()
        self.results["cpu_multi_thread"] = self.run_command(
            f"sysbench cpu --events=0 --time=30 --threads={cpu_count} run",
            f"CPU多线程测试 ({cpu_count}线程)",
        )

    def run_memory_test(self):
        """运行内存测试"""
        self.results["memory"] = self.run_command(
            "sysbench memory --threads=4 --time=30 --memory-block-size=1K --memory-total-size=100G run",
            "内存测试",
        )

    def run_fileio_tests(self):
        """运行文件IO测试"""
        # 准备文件
        self.results["fileio_prepare"] = self.run_command(
            "sysbench fileio --file-total-size=4G --file-num=4 prepare", "文件IO准备"
        )

        # 随机读写测试
        self.results["fileio_rndrw"] = self.run_command(
            "sysbench fileio --file-total-size=4G --file-num=4 --threads=4 --time=60 --file-test-mode=rndrw run",
            "文件IO随机读写测试",
        )

        # 顺序读取测试
        self.results["fileio_seqrd"] = self.run_command(
            "sysbench fileio --file-total-size=4G --file-num=4 --threads=4 --time=60 --file-test-mode=seqrd run",
            "文件IO顺序读取测试",
        )

        # 清理文件
        self.results["fileio_cleanup"] = self.run_command(
            "sysbench fileio --file-total-size=4G --file-num=4 cleanup", "文件IO清理"
        )

    def _parse_cpu_result(self, output: str) -> Dict:
        """解析CPU测试结果"""
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
        """解析内存测试结果"""
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
        """解析文件IO测试结果"""
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
        """保存测试结果"""
        # 保存原始JSON结果
        json_path = os.path.join(self.result_dir, "raw_results.json")
        with open(json_path, "w") as f:
            json.dump(self.results, f, indent=4)

        # 生成简化的人类可读报告
        report_path = os.path.join(self.result_dir, "report.txt")
        with open(report_path, "w") as f:
            f.write(f"Sysbench 性能测试报告（简化版）\n")
            f.write(f"测试时间: {self.timestamp}\n")
            f.write("=" * 50 + "\n\n")

            # CPU测试结果
            for test_name in ["cpu_single_thread", "cpu_multi_thread"]:
                if test_name in self.results and self.results[test_name]["status"] == "success":
                    result = self._parse_cpu_result(self.results[test_name]["output"])
                    f.write(f"\nCPU测试 - {'单线程' if 'single' in test_name else '多线程'}\n")
                    f.write("-" * 30 + "\n")
                    f.write(f"测试线程数: {result['threads']}\n")
                    f.write(f"测试时间: {result['time']}\n")
                    f.write(f"CPU速度: {result['events_per_second']} 事件/秒\n")

            # 内存测试结果
            if "memory" in self.results and self.results["memory"]["status"] == "success":
                result = self._parse_memory_result(self.results["memory"]["output"])
                f.write(f"\n内存测试\n")
                f.write("-" * 30 + "\n")
                f.write(f"测试选项: 块大小 {result['block_size']}\n")
                f.write(f"传输速度: {result['transfer_speed']}\n")
                f.write(f"总延迟: {result['latency_sum']}\n")

            # 文件IO测试结果
            for test_name in ["fileio_rndrw", "fileio_seqrd"]:
                if test_name in self.results and self.results[test_name]["status"] == "success":
                    result = self._parse_fileio_result(self.results[test_name]["output"])
                    f.write(f"\n硬盘测试 - {'随机读写' if 'rndrw' in test_name else '顺序读取'}\n")
                    f.write("-" * 30 + "\n")
                    f.write(f"读取速度: {result['read_throughput']} MiB/s\n")
                    if result["write_throughput"]:
                        f.write(f"写入速度: {result['write_throughput']} MiB/s\n")
                    f.write(f"总延迟: {result['latency_sum']} ms\n")

        print(f"\n测试完成！")
        print(f"详细结果已保存至: {self.result_dir}/")
        print(f"- 原始数据: {json_path}")
        print(f"- 简化报告: {report_path}")


def main():
    tester = SysbenchTester()

    print("开始执行Sysbench性能测试...")
    tester.run_cpu_tests()
    tester.run_memory_test()
    tester.run_fileio_tests()
    tester.save_results()


if __name__ == "__main__":
    main()
