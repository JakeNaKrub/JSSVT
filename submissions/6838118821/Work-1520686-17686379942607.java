package org.example;
public class Barbie extends Doll {
    public Barbie(String name, double price) {
        super(name, "plastic", price);
    }
    @Override
    public void play(){
        System.out.println("Barbie sings: I'm a barbie girl in a Barbie world");
    }
}