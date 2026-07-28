package bakery;

/**
 * A single pastry line held in stock, with a display name, a unit price in
 * pounds, and a {@link PastryType}.
 */
public class Pastry {

    private String name;
    private double price;
    private PastryType type;

    public Pastry(String name, double price, PastryType type) {
        this.name = name;
        this.price = price;
        this.type = type;
    }

    public String getName() {
        return name;
    }

    public double getPrice() {
        return price;
    }

    public PastryType getType() {
        return type;
    }
}
