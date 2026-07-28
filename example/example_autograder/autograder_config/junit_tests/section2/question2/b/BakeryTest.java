package section2.question2.b;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import bakery.Bakery;
import bakery.Pastry;
import bakery.PastryType;
import utils.FallbackChecker;

public class BakeryTest {

    static String FQCN = "bakery.Bakery";

    @BeforeAll
    public static void fallbackCheck() {
        FallbackChecker.skipIfFallback(FQCN);
    }

    @Test
    public void testAddPastryStoresPastry() {
        Bakery bakery = new Bakery("The Rising Crust");
        Pastry pastry = new Pastry("Almond Croissant", 2.80, PastryType.CROISSANT);
        bakery.addPastry(pastry);
        assertEquals(1, bakery.getPastries().size());
        assertTrue(bakery.getPastries().contains(pastry));
    }

    @Test
    public void testTotalStockValueIsZeroWhenEmpty() {
        Bakery bakery = new Bakery("The Rising Crust");
        assertEquals(0.0, bakery.totalStockValue(), 0.0001);
    }

    @Test
    public void testTotalStockValueSumsPrices() {
        Bakery bakery = new Bakery("The Rising Crust");
        bakery.addPastry(new Pastry("Almond Croissant", 2.80, PastryType.CROISSANT));
        bakery.addPastry(new Pastry("Cherry Scone", 1.90, PastryType.SCONE));
        assertEquals(4.70, bakery.totalStockValue(), 0.0001);
    }
}
