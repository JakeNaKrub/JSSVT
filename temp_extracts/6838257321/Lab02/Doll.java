

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
        return this.name;
    }

    public void play() {
        System.out.println("I don't know. How to play");
    }

    public void displayInfo() {
        System.out.println(String.format("Name: %s\nMaterial: %s\nPrice: $%f", this.name, this.material, this.price)); 
    }

    public Boolean isFragile() {
        return (this.material.equals("Porcelain") || this.material.equals("Glass"));
    }
}