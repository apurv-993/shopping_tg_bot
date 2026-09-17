from matcher import product_similarity


original = input("Original product: ")

print("\nEnter candidate products.")
print("Type 'done' when finished.\n")

while True:

    candidate = input("Candidate: ")

    if candidate.lower() == "done":
        break

    score = product_similarity(
        original,
        candidate
    )

    print(f"Match score: {score}%\n")