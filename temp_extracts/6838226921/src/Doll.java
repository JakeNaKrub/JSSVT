public class Doll {

    private String name;
    private String material;
    private double price;

    Doll(String name, String material, double price){
        this.name = name;
        this.material = material;
        this.price = price;
    }

    public String toString(){
        return this.name;
    }

    public void play(){
        System.out.println("I don't know. How to play");
    }

    public void displayInfo(){
        System.out.println("Name: " + this.name);
        System.out.println("Material: " + this.material);
        System.out.println("Price: $" + this.price);
    }

    public boolean isFragile(){
        if(this.material.equals("Porcelain") || this.material.equals("Glass")) {
            return true;
        }
        else {
            return false;
        }
    }
}
