package section1.question1.a;

import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import structural.StructuralHelper;
import utils.FallbackChecker;

public class PastryTypeTest {

    static String FQCN = "bakery.PastryType";

    @BeforeAll
    public static void fallbackCheck() {
        FallbackChecker.skipIfFallback(FQCN);
    }

    @Test
    public void testEnumExists() {
        assertTrue(StructuralHelper.classExists(FQCN));
    }

    @Test
    public void testEnumIsEnum() {
        assertTrue(StructuralHelper.classIsEnum(FQCN));
    }

    @Test
    @SuppressWarnings({"rawtypes", "unchecked"})
    public void testEnumValues() {
        Class<? extends Enum> clazz = (Class<? extends Enum>) StructuralHelper.getClass(FQCN);
        assertTrue(StructuralHelper.enumTypeContains(clazz, "CROISSANT"));
        assertTrue(StructuralHelper.enumTypeContains(clazz, "MUFFIN"));
        assertTrue(StructuralHelper.enumTypeContains(clazz, "SCONE"));
    }
}
