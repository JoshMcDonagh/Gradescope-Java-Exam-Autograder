package section2.question2.a;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Field;
import java.util.List;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import bakery.Bakery;
import structural.StructuralHelper;
import utils.FallbackChecker;

public class BakeryTest {

    static String FQCN = "bakery.Bakery";

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
    public void testPastriesFieldIsPrivateList() throws Exception {
        Field[] fields = StructuralHelper.getFields(FQCN);
        assertTrue(StructuralHelper.fieldExists("pastries", fields));
        assertTrue(StructuralHelper.fieldHasGenericType("pastries", fields,
                List.class, StructuralHelper.getClass("bakery.Pastry")));
    }

    @Test
    public void testConstructorExists() throws Exception {
        assertTrue(StructuralHelper.ctorExists(FQCN, String.class));
    }

    // --- Behaviour ---

    @Test
    public void testConstructorInitialisesEmptyList() {
        Bakery bakery = new Bakery("The Rising Crust");
        assertNotNull(bakery.getPastries());
        assertTrue(bakery.getPastries().isEmpty());
    }
}
