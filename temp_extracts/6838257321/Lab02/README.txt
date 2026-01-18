Instruction was quite unclear so I'll explain what I've modified to make the program works:

- There are 3 mentioned arguments: name, material, and price, but only the name and price are inputted as arguments in App.js which causes an error. Also, the instruction only said to override the play() function but does not mention overriding the material to Plastic, Fur, or Porcelain.

- This also contradicts with the other instruction that says to make all the values private which would make them inaccessible outside Doll.java so I added the material arguments manually to App.java

- Also, the prices' decimals are shortened due to the inputs being float but the datatype being double.

** I'm not sure if these are my fault but I thought I'd state them just in case.  **