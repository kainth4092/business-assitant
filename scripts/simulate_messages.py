#!/usr/bin/env python3
"""
Message Simulator Script: Dispatches 3 realistic client messages to Support Desk.
Demonstrates automated ticket creation, classification, root cause analysis,
and sandbox previewing for:
1. Data Issue (Category label fragmentation in sales table)
2. Code Bug (Discount calculation defect in demo_target)
3. Plain Question (Perishable return policy inquiry)
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

API_URL = os.environ.get("API_URL", "http://localhost:8000/support/messages")

SAMPLE_MESSAGES = [
  {
    "client_name": "Alex Chen",
    "client_email": "alex.chen@bigmart-retail.com",
    "channel": "slack",
    "message": "In the sales reports, LF and Low Fat are showing up as separate categories. Can you merge them?"
  },
  {
    "client_name": "David Miller",
    "client_email": "david.miller@bigmart-retail.com",
    "channel": "teams",
    "message": "The discount calculation in demo_target calculates the discounted price as price + discount instead of price - discount! Outlet totals are inflated."
  },
  {
    "client_name": "Elena Rostova",
    "client_email": "elena.r@bigmart-retail.com",
    "channel": "webhook",
    "message": "What is our store policy on customer returns for perishable dairy and meat items?"
  }
]

def send_message(payload):
    print(f"\n[Simulator] Sending message from {payload['client_name']} ({payload['channel']}):")
    print(f"  \"{payload['message']}\"")
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        start = time.time()
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = time.time() - start
            body = json.loads(resp.read().decode("utf-8"))
            print(f"  -> HTTP {resp.status} in {elapsed:.2f}s")
            print(f"  -> Ticket ID: {body.get('id')}")
            print(f"  -> Classification: {body.get('classification')} (confidence: {body.get('confidence')})")
            print(f"  -> Status: {body.get('status')}")
            if body.get("approval_token"):
                print(f"  -> Approval Token: {body.get('approval_token')}")
            if body.get("reply_message"):
                print(f"  -> Drafted Reply: {body.get('reply_message')[:100]}...")
            return body
    except urllib.error.URLError as e:
        print(f"  [ERROR] Request failed: {e}")
        return None

def main():
    print("=" * 70)
    print("Support Desk Client Message Simulator")
    print(f"Targeting: {API_URL}")
    print("=" * 70)

    results = []
    for sample in SAMPLE_MESSAGES:
        res = send_message(sample)
        if res:
            results.append(res)
        time.sleep(1)

    print("\n" + "=" * 70)
    print(f"Summary: Dispatched {len(results)}/{len(SAMPLE_MESSAGES)} simulated client tickets.")
    print("=" * 70)

if __name__ == "__main__":
    main()
