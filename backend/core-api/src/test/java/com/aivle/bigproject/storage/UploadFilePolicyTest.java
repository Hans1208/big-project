package com.aivle.bigproject.storage;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.aivle.bigproject.common.exception.BadRequestException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

// 업로드 파일 검증 규칙 테스트.
// 스프링 컨텍스트도 네트워크도 쓰지 않는다 — UploadFilePolicy는 정적 규칙만 담고 있다.
class UploadFilePolicyTest {

    @Nested
    @DisplayName("확장자")
    class Extension {

        @ParameterizedTest
        @ValueSource(strings = {"녹취.mp3", "녹취.wav", "녹취.m4a", "판결문.pdf", "소장.hwp",
                "소장.hwpx", "문서.doc", "문서.docx", "메모.txt", "증빙.jpg", "증빙.jpeg", "증빙.png"})
        @DisplayName("상담에서 실제로 받는 자료는 통과한다")
        void allowsExpectedTypes(String fileName) {
            assertThatCode(() -> UploadFilePolicy.validate(fileName, null, 1024L))
                    .doesNotThrowAnyException();
        }

        @ParameterizedTest
        @ValueSource(strings = {"악성.exe", "스크립트.sh", "웹셸.jsp", "웹셸.php", "배치.bat",
                "라이브러리.dll", "압축.zip", "설정.html"})
        @DisplayName("실행되거나 쓸 일이 없는 형식은 막는다")
        void rejectsDangerousTypes(String fileName) {
            assertThatThrownBy(() -> UploadFilePolicy.validate(fileName, null, 1024L))
                    .isInstanceOf(BadRequestException.class)
                    .hasMessageContaining("허용하지 않는 파일 형식");
        }

        @Test
        @DisplayName("확장자가 없으면 막는다")
        void rejectsMissingExtension() {
            assertThatThrownBy(() -> UploadFilePolicy.validate("확장자없음", null, 1024L))
                    .isInstanceOf(BadRequestException.class);
        }

        @Test
        @DisplayName("대문자 확장자도 통과한다")
        void allowsUppercaseExtension() {
            assertThatCode(() -> UploadFilePolicy.validate("녹취.MP3", null, 1024L))
                    .doesNotThrowAnyException();
        }

        @Test
        @DisplayName("확장자를 둘 붙여도 마지막 것으로 판단한다")
        void usesLastExtension() {
            // "이력서.pdf.exe" 같은 이름이 pdf로 통과하면 안 된다.
            assertThatThrownBy(() -> UploadFilePolicy.validate("이력서.pdf.exe", null, 1024L))
                    .isInstanceOf(BadRequestException.class);
        }
    }

    @Nested
    @DisplayName("확장자와 형식 일치")
    class ContentType {

        @Test
        @DisplayName("짝이 맞으면 통과한다")
        void allowsMatching() {
            assertThatCode(() -> UploadFilePolicy.validate("녹취.mp3", "audio/mpeg", 1024L))
                    .doesNotThrowAnyException();
        }

        @Test
        @DisplayName("어긋나면 막는다")
        void rejectsMismatch() {
            assertThatThrownBy(() -> UploadFilePolicy.validate("증빙.png", "application/pdf", 1024L))
                    .isInstanceOf(BadRequestException.class)
                    .hasMessageContaining("일치하지 않습니다");
        }

        @Test
        @DisplayName("charset이 붙어 있어도 본체만 보고 판단한다")
        void ignoresCharsetParameter() {
            assertThatCode(() -> UploadFilePolicy.validate("메모.txt", "text/plain; charset=utf-8", 1024L))
                    .doesNotThrowAnyException();
        }

        @Test
        @DisplayName("형식을 알 수 없으면 확장자를 따른다")
        void fallsBackToExtension() {
            // 일부 브라우저는 hwp/hwpx에 빈 값이나 octet-stream을 보낸다.
            assertThatCode(() -> UploadFilePolicy.validate("소장.hwp", "application/octet-stream", 1024L))
                    .doesNotThrowAnyException();
            assertThatCode(() -> UploadFilePolicy.validate("소장.hwp", "", 1024L))
                    .doesNotThrowAnyException();
            assertThatCode(() -> UploadFilePolicy.validate("소장.hwp", null, 1024L))
                    .doesNotThrowAnyException();
        }

        @Test
        @DisplayName("형식이 맞아도 확장자가 허용 목록에 없으면 막는다")
        void extensionStillWins() {
            // 확장자 검사가 먼저다 — contentType만 믿으면 우회된다.
            assertThatThrownBy(() -> UploadFilePolicy.validate("악성.exe", "application/pdf", 1024L))
                    .isInstanceOf(BadRequestException.class)
                    .hasMessageContaining("허용하지 않는 파일 형식");
        }
    }

    @Nested
    @DisplayName("파일명 정리")
    class FileName {

        @Test
        @DisplayName("경로 문자를 없애고 마지막 조각만 남긴다")
        void stripsPath() {
            // S3 key에 '/'가 들어가면 의도하지 않은 위치에 오브젝트가 생긴다.
            assertThat(UploadFilePolicy.sanitizeFileName("../../etc/passwd.txt")).isEqualTo("passwd.txt");
            assertThat(UploadFilePolicy.sanitizeFileName("C:\\temp\\녹취.mp3")).isEqualTo("녹취.mp3");
            assertThat(UploadFilePolicy.sanitizeFileName("a/b/c/문서.pdf")).isEqualTo("문서.pdf");
        }

        @Test
        @DisplayName("개행과 널 문자를 없앤다")
        void stripsControlCharacters() {
            // 응답 헤더에 그대로 실리면 헤더가 쪼개질 수 있다.
            assertThat(UploadFilePolicy.sanitizeFileName("녹취\r\n.mp3")).isEqualTo("녹취.mp3");
            assertThat(UploadFilePolicy.sanitizeFileName("녹취\u0000.mp3")).isEqualTo("녹취.mp3");
        }

        @Test
        @DisplayName("앞의 점을 없앤다")
        void stripsLeadingDots() {
            assertThat(UploadFilePolicy.sanitizeFileName("...메모.txt")).isEqualTo("메모.txt");
        }

        @Test
        @DisplayName("한글 이름은 그대로 둔다")
        void keepsKorean() {
            assertThat(UploadFilePolicy.sanitizeFileName("상속 한정승인 녹취.mp3"))
                    .isEqualTo("상속 한정승인 녹취.mp3");
        }

        @Test
        @DisplayName("너무 길면 확장자를 지키면서 자른다")
        void truncatesKeepingExtension() {
            String longName = "가".repeat(300) + ".pdf";
            String result = UploadFilePolicy.sanitizeFileName(longName);
            assertThat(result).endsWith(".pdf");
            assertThat(result.length()).isLessThanOrEqualTo(150);
        }

        @Test
        @DisplayName("정리하고 나면 아무것도 안 남는 이름은 막는다")
        void rejectsEmptyAfterSanitize() {
            assertThatThrownBy(() -> UploadFilePolicy.sanitizeFileName("///"))
                    .isInstanceOf(BadRequestException.class);
            assertThatThrownBy(() -> UploadFilePolicy.sanitizeFileName(null))
                    .isInstanceOf(BadRequestException.class);
        }

        @Test
        @DisplayName("경로를 붙여도 확장자 검사를 통과하지 못한다")
        void pathTraversalStillValidated() {
            assertThatThrownBy(() -> UploadFilePolicy.validate("../../웹셸.jsp", null, 1024L))
                    .isInstanceOf(BadRequestException.class);
        }
    }

    @Nested
    @DisplayName("크기")
    class Size {

        @Test
        @DisplayName("상한을 넘으면 막는다")
        void rejectsTooLarge() {
            assertThatThrownBy(() ->
                    UploadFilePolicy.validate("녹취.mp3", "audio/mpeg", UploadFilePolicy.MAX_SIZE_BYTES + 1))
                    .isInstanceOf(BadRequestException.class)
                    .hasMessageContaining("너무 큽니다");
        }

        @Test
        @DisplayName("상한과 같으면 통과한다")
        void allowsExactLimit() {
            assertThatCode(() ->
                    UploadFilePolicy.validate("녹취.mp3", "audio/mpeg", UploadFilePolicy.MAX_SIZE_BYTES))
                    .doesNotThrowAnyException();
        }

        @Test
        @DisplayName("크기를 안 보내면 크기 검사만 건너뛴다")
        void skipsWhenUnknown() {
            // 구버전 프론트 호환. 형식 검사는 그대로 걸린다.
            assertThatCode(() -> UploadFilePolicy.validate("녹취.mp3", "audio/mpeg", null))
                    .doesNotThrowAnyException();
            assertThatThrownBy(() -> UploadFilePolicy.validate("악성.exe", null, null))
                    .isInstanceOf(BadRequestException.class);
        }
    }
}
