output = ""

for i in range(1, 91):
    output += "screen." + str(i) + "\n"
    output += open("xsokoban/screen."+str(i)).read()
    output += "\n\n"

print(output)
