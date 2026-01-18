public class PorcelainDoll extends Doll {

    PorcelainDoll(String name, String material, double price){
        super(name, material, price);
    }

    @Override
    public void play(){
        System.out.println("Porcelain Doll is delicate, be gentle!");
    }
}
