public class PorcelainDoll extends Doll{
    public PorcelainDoll (String name, String material, double price){
        super(name,material,price);

    }

    public void play() {
        System.out.println("Porcelain Doll is delicate, be gentle!");
    }
}