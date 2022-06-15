import random

for i in range(1000):
    s = set(random.sample(range(1000), i))

    for a, b in zip(s, sorted(s)):
        if a == b:
            continue

        print("Not sorted: ", i)
        print(s)
        break
