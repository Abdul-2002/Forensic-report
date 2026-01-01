n = 5
k = 1

for i in range(1,n):
    sp=n-k
    while sp >0:
        print("_",end="")
        sp-=1
    for j in range(0,i):
        print("*",end="")
    sp=n-k
    while sp >0:
        print("_",end="")
        sp-=1
    k+=1
    print()