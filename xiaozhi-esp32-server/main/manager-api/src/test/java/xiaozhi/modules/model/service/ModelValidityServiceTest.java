package xiaozhi.modules.model.service;
import org.junit.jupiter.api.Test;
import cn.hutool.json.JSONObject;
import xiaozhi.modules.model.entity.ModelConfigEntity;
import xiaozhi.common.exception.RenException;
import static org.junit.jupiter.api.Assertions.*;

class ModelValidityServiceTest {
    private ModelConfigEntity model(String status, int enabled, String key) {
        var m = new ModelConfigEntity();
        m.setModelType("LLM"); m.setValidityStatus(status); m.setIsEnabled(enabled); m.setIsDefault(1);
        m.setConfigJson(new JSONObject().set("api_key", key));
        m.setValidityCheckedAt(new java.util.Date());
        return m;
    }
    @Test void invalidAndUnknownCannotEnable() {
        for (String status : new String[]{"invalid", "unknown", null}) {
            assertThrows(RenException.class, () -> ModelValidityService.requireValid(model(status, 0, "test")));
        }
        assertDoesNotThrow(() -> ModelValidityService.requireValid(model("valid", 0, "test")));
    }
    @Test void changedCredentialsInvalidatePriorSuccessAndDisableDefault() {
        var before = model("valid", 1, "old"); var after = model("valid", 1, "new");
        ModelValidityService.applyEditPolicy(before, after);
        assertEquals("unknown", after.getValidityStatus());
        assertEquals(0, after.getIsEnabled()); assertEquals(0, after.getIsDefault());
        assertNull(after.getValidityCheckedAt());
    }
    @Test void nameOnlyChangeRetainsEvidence() {
        var before = model("valid", 1, "same"); var after = model("valid", 1, "same");
        after.setModelName("新名称"); ModelValidityService.applyEditPolicy(before, after);
        assertEquals("valid", after.getValidityStatus()); assertEquals(1, after.getIsEnabled());
    }
    @Test void editCannotBypassEnableGuardButCanDisable() {
        var before = model("invalid", 0, "same"); var after = model("invalid", 1, "same");
        assertThrows(RenException.class, () -> ModelValidityService.applyEditPolicy(before, after));
        after.setIsEnabled(0);
        assertDoesNotThrow(() -> ModelValidityService.applyEditPolicy(before, after));
    }
}
