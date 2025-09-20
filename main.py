import requests
import json
import random
import time
from eth_account.messages import encode_defunct
from web3 import Web3
from datetime import datetime, timedelta

# --- 1. 配置部分 (请根据你的需要修改) ---
# 你需要邀请的用户数量 (1-100)
NUM_USERS_TO_INVITE = 5

# API 接口 URL
CHALLENGE_URL = "https://api.falcon.finance/api/v1/wallets/challenge"
SIGN_IN_URL = "https://api.falcon.finance/api/v1/wallets/sign_in"

# 初始化 Web3 实例
w3 = Web3()

def load_data_from_file(filename):
    """从文件中加载数据，每行一个项目，并过滤空行和注释行。"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            return lines
    except FileNotFoundError:
        print(f"错误: 找不到文件 {filename}。请确保文件存在。")
        return []

# 从 txt 文件中加载邀请码和代理
INVITE_CODES = load_data_from_file("invites.txt")
PROXY_LIST = load_data_from_file("proxies.txt")

def make_request_with_retry(method, url, max_retries=3, timeout=30, **kwargs):
    """带重试机制的网络请求函数"""
    for attempt in range(max_retries):
        try:
            if method.upper() == 'GET':
                response = requests.get(url, timeout=timeout, **kwargs)
            elif method.upper() == 'POST':
                response = requests.post(url, timeout=timeout, **kwargs)
            else:
                raise ValueError(f"不支持的请求方法: {method}")
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                raise
            print(f"请求超时，正在重试 ({attempt + 1}/{max_retries})...")
            time.sleep(2 ** attempt)  # 指数退避
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            print(f"请求失败，正在重试 ({attempt + 1}/{max_retries})... 错误: {e}")
            time.sleep(2 ** attempt)

def process_single_invite(referral_code, proxy):
    """处理单个邀请任务的完整流程"""
    task_start_time = time.time()
    
    proxies = None
    if proxy:
        proxies = {"http": proxy, "https": proxy}
    
    # 生成一个全新的钱包地址和私钥
    account = w3.eth.account.create()
    new_address = account.address
    private_key = account.key.hex()
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在处理邀请码: {referral_code}，钱包: {new_address}")
        if proxy:
            print(f"使用代理: {proxy}")
        
        # --- 步骤 1: 获取签名挑战 ---
        challenge_params = {
            "address": new_address,
            "challenge_type": "sign_in"
        }
        
        print("正在获取签名挑战...")
        response = make_request_with_retry('GET', CHALLENGE_URL, params=challenge_params, proxies=proxies)
        
        challenge_data = response.json()
        challenge_message = challenge_data["challenge"]
        print(f"获取到挑战消息: {challenge_message[:50]}...")
        
        # --- 步骤 2: 使用私钥进行签名 ---
        print("正在生成签名...")
        message = encode_defunct(text=challenge_message)
        signed_message = w3.eth.account.sign_message(message, private_key=private_key)
        signature = signed_message.signature.hex()
        
        # --- 3. 提交签名和邀请码，完成登录 ---
        signin_params = {
            "address": new_address,
            "challenge": challenge_message,
            "signature": signature,
            "signature_type": "eoa",
            "referral": referral_code
        }
        
        print("正在提交登录请求...")
        response = make_request_with_retry('POST', SIGN_IN_URL, params=signin_params, proxies=proxies)
        
        # 任务成功
        elapsed_time = time.time() - task_start_time
        print(f"✅ 成功! 邀请码 {referral_code} 绑定新用户: {new_address}。耗时: {elapsed_time:.2f}秒")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 失败! 邀请码 {referral_code} 网络请求失败。原因: {e}")
    except Exception as e:
        print(f"❌ 失败! 邀请码 {referral_code} 发生未知错误。原因: {e}")

# --- 主程序入口 ---
def main():
    print("=== Falcon 拉新脚本启动 ===")
    
    if not INVITE_CODES:
        print("错误: 邀请码列表为空。请检查 invites.txt 文件并添加有效的邀请码。")
        print("提示: 请确保 invites.txt 文件存在且包含有效的邀请码，每行一个。")
        return
    
    if not PROXY_LIST:
        print("警告: 代理列表为空，脚本将不使用代理。")
        print("提示: 如需使用代理，请在 proxies.txt 文件中添加代理地址。")
    
    print(f"--- 准备开始邀请，目标人数: {NUM_USERS_TO_INVITE} ---")
    print(f"可用邀请码数量: {len(INVITE_CODES)}")
    print(f"可用代理数量: {len(PROXY_LIST)}")
    
    for i in range(NUM_USERS_TO_INVITE):
        print(f"\n--- 开始第 {i+1}/{NUM_USERS_TO_INVITE} 个邀请任务 ---")
        
        # 随机选择一个邀请码
        referral_code = random.choice(INVITE_CODES)
        
        current_proxy = None
        if PROXY_LIST:
            # 按顺序选择代理，使用取模运算实现循环
            proxy_index = i % len(PROXY_LIST)
            current_proxy = PROXY_LIST[proxy_index]
        
        # 执行单个邀请流程
        process_single_invite(referral_code, current_proxy)
        
        # 随机延迟，模拟真实用户行为
        if i < NUM_USERS_TO_INVITE - 1:
            delay = random.randint(10, 60)  # 减少延迟时间到10-60秒
            print(f"等待 {delay} 秒后继续下一个任务...⏳")
            time.sleep(delay)
    
    print("\n=== 所有任务已完成 ===")

if __name__ == "__main__":
    main()