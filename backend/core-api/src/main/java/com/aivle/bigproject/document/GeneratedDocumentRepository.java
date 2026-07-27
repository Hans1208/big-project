package com.aivle.bigproject.document;

import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface GeneratedDocumentRepository extends JpaRepository<GeneratedDocument, Long> {

    List<GeneratedDocument> findByConsultationId(Long consultationId);

    void deleteByConsultationId(Long consultationId);
}
