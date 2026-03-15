package tr.org.lider.platform.compat;

import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class PlatformRequestExceptionHandler {

    private static final Logger logger = LoggerFactory.getLogger(PlatformRequestExceptionHandler.class);

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<String> handleIllegalArgumentException(
            IllegalArgumentException exception,
            HttpServletRequest request
    ) {
        String requestUri = request.getRequestURI();
        String message = exception.getMessage();

        if (message != null && message.contains("argument \"content\" is null")) {
            if (requestUri.endsWith("/api/lider/computer-groups/create-new-agent-group")) {
                logger.warn("Rejected computer group creation with empty selection payload");
                return ResponseEntity
                        .status(HttpStatus.NOT_ACCEPTABLE)
                        .body("Seçili klasörlerde istemci bulunamadı. Lütfen en az bir istemci seçiniz.");
            }

            if (requestUri.endsWith("/api/lider/user-groups/create-new-group")) {
                logger.warn("Rejected user group creation with empty selection payload");
                return ResponseEntity
                        .status(HttpStatus.NOT_ACCEPTABLE)
                        .body("Seçili klasörlerde kullanıcı bulunamadı. Lütfen en az bir kullanıcı seçiniz.");
            }
        }

        throw exception;
    }
}
