package ComprogLab2;

public class Doll {
    private String name;
    private String material;
    private double price;

    public Doll(String name, String material, double price) {
      this.name = name;
      this.material = material;
      this.price = price;
    }

    public String toString() {
      return name;
    }

    public void play() {
      System.out.println("I don't know. How to play");
    }

    public void displayInfo() {
      System.out.println("Name: " + name);
      System.out.println("Material: " + material);
      System.out.println("Price: " + "$" + price);
    }

    public boolean isFragile() {
      if (material.equals("Porcelain") || material.equals("Glass")) {
        return true;
      }
      else {
        return false;
      }
    }
}
