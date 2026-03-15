package tr.org.lider.security;

import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;
import org.springframework.security.crypto.argon2.Argon2PasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

/**
 * Password Encoder — Argon2 + SSHA desteği
 * 
 * LDAP bind uyumluluğu için SSHA hash formatını da destekler.
 * Üretim ortamlarında şifre SSHA ile LDAP'a kaydedilir,
 * LiderAPI hem SSHA hem Argon2 ile karşılaştırma yapabilir.
 */

@Service
public class CustomPasswordEncoder implements PasswordEncoder {

    Argon2PasswordEncoder argon2Encoder = Argon2PasswordEncoder.defaultsForSpringSecurity_v5_8();

    @Override
    public String encode(CharSequence rawPassword) {
        return argon2Encoder.encode(String.valueOf(rawPassword));
    }

    @Override
    public boolean matches(CharSequence rawPassword, String encodedPassword) {
        if (encodedPassword == null || encodedPassword.isEmpty()) {
            return false;
        }
        
        // SSHA formatı: {SSHA}base64(SHA1(password+salt)+salt)
        if (encodedPassword.startsWith("{SSHA}")) {
            return matchesSsha(rawPassword, encodedPassword);
        }
        
        // Argon2 formatı (eski tag'ı kaldır)
        if (encodedPassword.startsWith("{ARGON2}")) {
            encodedPassword = encodedPassword.replace("{ARGON2}", "");
        }
        
        try {
            return argon2Encoder.matches(rawPassword, encodedPassword);
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * SSHA (Salted SHA-1) karşılaştırma — OpenLDAP uyumlu
     */
    private boolean matchesSsha(CharSequence rawPassword, String encodedPassword) {
        try {
            String base64 = encodedPassword.substring(6); // {SSHA} kaldır
            byte[] decoded = Base64.getDecoder().decode(base64);
            
            // SHA-1 digest 20 byte, geri kalanı salt
            byte[] digestBytes = new byte[20];
            byte[] salt = new byte[decoded.length - 20];
            System.arraycopy(decoded, 0, digestBytes, 0, 20);
            System.arraycopy(decoded, 20, salt, 0, salt.length);
            
            // Aynı salt ile yeniden hash'le
            MessageDigest md = MessageDigest.getInstance("SHA-1");
            md.update(String.valueOf(rawPassword).getBytes("UTF-8"));
            md.update(salt);
            byte[] computed = md.digest();
            
            return MessageDigest.isEqual(digestBytes, computed);
        } catch (Exception e) {
            return false;
        }
    }
}
