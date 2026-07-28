package section1.question1.b;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import bakery.Pastry;
import bakery.PastryType;
import structural.AccessType;
import structural.StructuralHelper;
import utils.FallbackChecker;

public class PastryTest {

    static String FQCN = "bakery.Pastry";

    @BeforeAll
    public static void fallbackCheck() {
        FallbackChecker.skipIfFallback(FQCN);
    }

    // --- Structure ---

    @Test
    public void testClassExists() {
        assertTrue(StructuralHelper.classExists(FQCN));
    }

    @Test
    public void testClassIsPublic() {
        assertTrue(StructuralHelper.classIsPublic(FQCN));
    }

    @Test
    public void testNameFieldIsPrivate() throws Exception {
        Field[] fields = StructuralHelper.getFields(FQCN);
        assertTrue(StructuralHelper.fieldExists("name", fields));
        assertTrue(StructuralHelper.fieldAccessIsAccessType("name", fields, AccessType.PRIVATE));
    }

    @Test
    public void testPriceFieldHasDoubleType() throws Exception {
        Field[] fields = StructuralHelper.getFields(FQCN);
        assertTrue(StructuralHelper.fieldHasType("price", fields, double.class));
    }

    @Test
    public void testConstructorExists() throws Exception {
        assertTrue(StructuralHelper.ctorExists(FQCN,
                String.class, double.class, StructuralHelper.getClass("bakery.PastryType")));
    }

    @Test
    public void testGetPriceReturnsDouble() throws Exception {
        Method[] methods = StructuralHelper.getMethods(FQCN);
        assertTrue(StructuralHelper.methodHasReturnType("getPrice", methods, double.class));
    }

    // --- Behaviour ---

    @Test
    public void testConstructorStoresName() {
        Pastry pastry = new Pastry("Almond Croissant", 2.80, PastryType.CROISSANT);
        assertEquals("Almond Croissant", pastry.getName());
    }

    @Test
    public void testConstructorStoresPrice() {
        Pastry pastry = new Pastry("Blueberry Muffin", 2.20, PastryType.MUFFIN);
        assertEquals(2.20, pastry.getPrice(), 0.0001);
    }

    @Test
    public void testConstructorStoresType() {
        Pastry pastry = new Pastry("Cherry Scone", 1.90, PastryType.SCONE);
        assertEquals(PastryType.SCONE, pastry.getType());
    }
}
