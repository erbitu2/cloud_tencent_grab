import requests
from datetime import datetime, timedelta
import time
import random
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

session = requests.Session()
US_COOKIE = ""
CSRF = "0"
headers = {}
quyu_id = [1, 4, 8]


def parse_cookie_str(cookie_str):
    cookie_dict = {}
    if not cookie_str:
        return cookie_dict
    parts = cookie_str.split("; ")
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            cookie_dict[k] = v
    return cookie_dict


def compute_csrf(skey: str) -> str:
    if not skey:
        return ""
    n = 5381
    for ch in skey:
        n += (n << 5) + ord(ch)
    return str(2147483647 & n)


def get_today_ms(hms_str) -> list[int]:
    today = datetime.now().strftime("%Y-%m-%d")
    ts_list = []
    for t_str in hms_str:
        full = f"{today} {t_str}"
        t = time.strptime(full, "%Y-%m-%d %H:%M:%S")
        ms = int(time.mktime(t) * 1000)
        ts_list.append(ms)
    return ts_list


def get_server_time():
    return int(time.time() * 1000)


def init_cookie(cookie_str):
    global US_COOKIE, CSRF, headers
    US_COOKIE = cookie_str
    ck = parse_cookie_str(US_COOKIE)
    skey = ck.get("skey", "")
    CSRF = compute_csrf(skey)
    username = ck.get("nick", "未知用户")
    try:
        username = urllib.parse.unquote(username)
    except Exception:
        pass
    print(f"✅ Cookie初始化完成")
    print(f"   CSRF Token: {CSRF}")
    print(f"   用户名: {username}")
    headers = {
        "x-csrf-token": str(CSRF),
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "referer": "https://cloud.tencent.com/act/pro/featured-202607?fromSource=gwzcw.15211855.15211855.15211855&utm_medium=cpc&utm_id=gwzcw.15211855.15211855.15211855#CVM"
    }


def task(region_id):
    global US_COOKIE, CSRF, headers
    print(f"调用抢购任务 region_id={region_id}")
    do_data = {
        "activity_id": 164461404341040,
        "agent_channel": {
            "fromChannel": "",
            "fromSales": "",
            "isAgentClient": False,
            "fromUrl": "https://cloud.tencent.com/act/pro/featured-202607?fromSource=gwzcw.15211855.15211855.15211855&utm_medium=cpc&utm_id=gwzcw.15211855.15211855.15211855"
        },
        "business": {
            "id": 189763,
            "from": "lightningDeals"
        },
        "goods": [
            {
                "act_id": 1897632168296710,
                "type": "bundle_budget_mc_lg4_01",
                "goods_param": {
                    "BlueprintId": "LINUX_UNIX",
                    "area": 1,
                    "ddocUnionConnect": 0,
                    "goodsNum": 1,
                    "imageId": "lhbp-eqora508",
                    "scenario": "0",
                    "timeSpanUnit": "12m",
                    "zone": "",
                    "regionId": region_id,
                    "type": "bundle_budget_mc_lg4_01"
                }
            }
        ],
        "preview": 0
    }
    retry_count = 0
    max_retries = 30
    retry_interval = 0.05
    timeout_retry_count = 0
    max_timeout_retries = 3
    while retry_count < max_retries:
        try:
            ck_dict = parse_cookie_str(US_COOKIE)
            resp = session.post(
                "https://act-api.cloud.tencent.com/dianshi/do-goods",
                json=do_data,
                headers=headers,
                timeout=5,
                cookies=ck_dict
            )
            raw_text = resp.text[:1000]
            try:
                json_res = resp.json()
                json_res["region_id"] = region_id
                json_res["raw_response"] = raw_text
                json_res["exception"] = ""

                code = json_res.get("code")
                if code == 1101001:
                    retry_count += 1
                    print(f"⏳ region{region_id} 秒杀尚未开始，重试第{retry_count}/{max_retries}次")
                    time.sleep(retry_interval)
                    continue

                print(f"🎯 region{region_id} 抢购接口返回：code={code} msg={json_res.get('msg', '')}")
                return json_res
            except ValueError:
                return {"code": -99, "msg": "接口非JSON返回", "region_id": region_id, "raw_response": raw_text,
                        "exception": ""}
        except Exception as e:
            err_msg = str(e)
            if "timeout" in err_msg.lower():
                timeout_retry_count += 1
                if timeout_retry_count <= max_timeout_retries:
                    print(f"⏳ region{region_id} 请求超时，重试第{timeout_retry_count}/{max_timeout_retries}次")
                    time.sleep(0.1)
                    continue
                else:
                    print(f"❌ region{region_id} 请求超时({err_msg})，已达最大重试次数")
                    return {"code": -999, "msg": "请求超时", "region_id": region_id, "raw_response": "",
                            "exception": "timeout"}
            print(f"❌ region{region_id} 抢购接口调用失败：{err_msg}")
            return {"code": -999, "msg": f"接口调用失败: {err_msg[:100]}", "region_id": region_id, "raw_response": "",
                    "exception": err_msg[:100]}

    return {"code": -998, "msg": f"重试{max_retries}次后仍未开始", "region_id": region_id, "raw_response": "",
            "exception": ""}


def buy_now_concurrent():
    success_flag = False
    success_region = None
    success_result = None
    fail_messages = []
    region_ids = quyu_id
    print(f"\n🚀 开始并发抢购，地域列表: {region_ids}")
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(task, rid) for rid in region_ids]
        for future in futures:
            result = future.result()
            rid = result.get("region_id", "未知")
            if result.get("code") == 0:
                success_flag = True
                success_region = rid
                success_result = result
                print(f"🎉 地域{rid}抢购成功！完整返回：{result}")
            else:
                msg = result.get("msg", "未知错误")
                fail_messages.append(f"地域{rid}: {msg}")
                print(f"地域 {rid} 抢购失败: {msg}")
    return success_flag, success_result


if __name__ == '__main__':
    Config_SECKILL_TIME = ["09:59:58", "14:59:58"]
    RETRY_DELAY = 300
    day_record = {
        "current_day": None,
        "already_seckill": [False, False]
    }

    cookie_input = input("请输入腾讯云Cookie：").strip()
    if not cookie_input:
        print("❌ Cookie不能为空！")
        exit(1)
    init_cookie(cookie_input)

    print("\n📋 可选地域列表:")
    print("   1 - 广州")
    print("   4 - 上海")
    print("   8 - 北京")
    region_input = input("请输入地域ID (默认三个地域随机）：").strip()
    if region_input:
        try:
            region_list = [int(x.strip()) for x in region_input.split(",")]
            if len(region_list) == 1:
                quyu_id = [region_list[0], region_list[0], region_list[0]]
            else:
                quyu_id = region_list
            print(f"✅ 已选择地域: {quyu_id}")
        except ValueError:
            print("❌ 地域ID输入格式错误，使用默认地域")
            quyu_id = [1, 4, 8]
    else:
        quyu_id = [1, 4, 8]
        print(f"✅ 使用默认地域: {quyu_id}")

    print("=====腾讯云定时抢购脚本启动=====")
    print(f"抢购时间: {Config_SECKILL_TIME}")
    print(f"重试间隔: {RETRY_DELAY/1000}秒")

    while True:
        now_day = datetime.now().strftime("%Y-%m-%d")
        if day_record["current_day"] != now_day:
            day_record["current_day"] = now_day
            day_record["already_seckill"] = [False, False]
            print(f"\n📅 新的一天: {now_day}，重置抢购状态")

        SECKILL_TIMESTAMP = get_today_ms(Config_SECKILL_TIME)
        host_time = int(time.time() * 1000)
        PRE_HEAD = 60000
        POST_ALLOW = 3000
        RAND1_MIN, RAND1_MAX = 800, 1100
        RAND2_MIN, RAND2_MAX = 200, 800

        s1 = SECKILL_TIMESTAMP[0]
        s1_start = s1 - PRE_HEAD
        s1_end = s1 + POST_ALLOW
        if s1_start <= host_time < s1_end:
            if not day_record["already_seckill"][0]:
                tx_time = get_server_time()
                trigger = s1 - random.randint(RAND1_MIN, RAND1_MAX)
                if trigger <= tx_time <= s1 + POST_ALLOW:
                    day_record["already_seckill"][0] = True
                    print("\n🔥 疯狂抢购啦！第一场执行并发抢购")
                    success, result = buy_now_concurrent()
                    if not success:
                        print(f"\n⏳ 第一场抢购失败，{RETRY_DELAY/1000}秒后进行第二次尝试...")
                        time.sleep(RETRY_DELAY / 1000)
                        print("\n🔥 第二次尝试抢购！")
                        buy_now_concurrent()
                    else:
                        print("\n🎉 抢购成功！等待明天继续...")

        s2 = SECKILL_TIMESTAMP[1]
        s2_start = s2 - PRE_HEAD
        s2_end = s2 + POST_ALLOW
        if s2_start <= host_time < s2_end:
            if not day_record["already_seckill"][1]:
                tx_time = get_server_time()
                trigger = s2 - random.randint(RAND2_MIN, RAND2_MAX)
                if trigger <= tx_time <= s2 + POST_ALLOW:
                    day_record["already_seckill"][1] = True
                    print("\n🔥 疯狂抢购啦！第二场执行并发抢购")
                    success, result = buy_now_concurrent()
                    if not success:
                        print(f"\n⏳ 第二场抢购失败，{RETRY_DELAY/1000}秒后进行第二次尝试...")
                        time.sleep(RETRY_DELAY / 1000)
                        print("\n🔥 第二次尝试抢购！")
                        buy_now_concurrent()
                    else:
                        print("\n🎉 抢购成功！等待明天继续...")

        diff1 = abs(host_time - s1)
        diff2 = abs(host_time - s2)
        min_diff = min(diff1, diff2)
        if min_diff > 30000:
            time.sleep(1)
        elif min_diff > 5000:
            time.sleep(0.3)
        else:
            time.sleep(0.05)
