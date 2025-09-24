import sys
import yaml

def main():
    try:
        # roadmap.yaml を読み込み
        with open("roadmap.yaml", "r") as f:
            data = yaml.safe_load(f)

        # 必須キーがなければエラー
        if not isinstance(data, dict) or "stages" not in data:
            raise ValueError("roadmap.yaml missing 'stages' key")

        print("✅ Consistency check passed")

    except Exception as e:
        # エラーメッセージを標準出力に出す
        print(f"❌ Consistency check failed: {e}")
        sys.exit(1)  # ← 非ゼロ終了コードを返す

if __name__ == "__main__":
    main()
