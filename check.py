import sys
sys.path.insert(0, "src")

from sei_voice_agent.services.responder import normalize_voice_text

# Test 1 — numbered list
print(normalize_voice_text("1. Log in to your Wise account\n2. Go to **Home**\n3. Click the transfer"))
print("---")

# Test 2 — bullet dashes
print(normalize_voice_text("- Your money is being processed\n- Money received\n- Transfer sent"))
print("---")

# Test 3 — bold markdown + URL
print(normalize_voice_text("Check **Home** in your account at https://wise.com/login to see your activity."))
print("---")

# Test 4 — clean text, should pass through unchanged
print(normalize_voice_text("Your transfer is on its way to the recipient bank."))