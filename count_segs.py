import json

with open('outputs/step3/step3_final_transcript.json', 'r') as f:
    plan_data = json.load(f)

segments = plan_data.get("segments", [])
print(f"Total segments in JSON: {len(segments)}")

for i, seg in enumerate(segments):
    order = seg.get("order")
    print(f"Index {i}, Order {order}, render_type {seg.get('render_type')}")
