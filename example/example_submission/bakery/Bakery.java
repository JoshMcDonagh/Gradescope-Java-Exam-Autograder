package bakery;

import java.util.ArrayList;
import java.util.List;

/**
 * A bakery holding a list of pastries in stock.
 */
public class Bakery {

    private String name;
    private List<Pastry> pastries;

    public Bakery(String name) {
        this.name = name;
        this.pastries = new ArrayList<>();
    }

    public String getName() {
        return name;
    }

    public List<Pastry> getPastries() {
        return pastries;
    }

    public void addPastry(Pastry pastry) {
        pastries.add(pastry);
    }

    public double totalStockValue() {
        double total = 0.0;
        for (Pastry pastry : pastries) {
            total += pastry.getPrice();
        }
        return total;
    }
}
