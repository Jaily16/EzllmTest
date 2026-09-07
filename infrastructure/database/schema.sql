-- MySQL dump 10.13  Distrib 8.0.29, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: ezllmtest_dev
-- ------------------------------------------------------
-- Server version	8.0.29

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `tb_project_design_testdoc`
--

DROP TABLE IF EXISTS `tb_project_design_testdoc`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_project_design_testdoc` (
  `id` char(21) NOT NULL,
  `path` varchar(500) NOT NULL,
  PRIMARY KEY (`id`,`path`),
  CONSTRAINT `tb_project_design_testdoc_tb_test_project_null_fk` FOREIGN KEY (`id`) REFERENCES `tb_test_project` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_project_design_testdoc`
--

LOCK TABLES `tb_project_design_testdoc` WRITE;
/*!40000 ALTER TABLE `tb_project_design_testdoc` DISABLE KEYS */;
/*!40000 ALTER TABLE `tb_project_design_testdoc` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tb_project_info`
--

DROP TABLE IF EXISTS `tb_project_info`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_project_info` (
  `id` char(21) NOT NULL,
  `info_type` int NOT NULL,
  `info` text NOT NULL,
  PRIMARY KEY (`id`,`info_type`),
  CONSTRAINT `tb_project_info_tb_test_project_null_fk` FOREIGN KEY (`id`) REFERENCES `tb_test_project` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='记录分析过程中重要的中间信息';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_project_info`
--

LOCK TABLES `tb_project_info` WRITE;
/*!40000 ALTER TABLE `tb_project_info` DISABLE KEYS */;
/*!40000 ALTER TABLE `tb_project_info` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tb_project_knowledge`
--

DROP TABLE IF EXISTS `tb_project_knowledge`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_project_knowledge` (
  `id` char(21) NOT NULL,
  `path` varchar(500) NOT NULL,
  PRIMARY KEY (`id`,`path`),
  CONSTRAINT `tb_project_knowledge_tb_test_project_null_fk` FOREIGN KEY (`id`) REFERENCES `tb_test_project` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_project_knowledge`
--

LOCK TABLES `tb_project_knowledge` WRITE;
/*!40000 ALTER TABLE `tb_project_knowledge` DISABLE KEYS */;
/*!40000 ALTER TABLE `tb_project_knowledge` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tb_project_requirement_testdoc`
--

DROP TABLE IF EXISTS `tb_project_requirement_testdoc`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_project_requirement_testdoc` (
  `id` char(21) NOT NULL,
  `path` varchar(500) NOT NULL,
  PRIMARY KEY (`id`,`path`),
  CONSTRAINT `tb_project_testdoc_tb_test_project_null_fk` FOREIGN KEY (`id`) REFERENCES `tb_test_project` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_project_requirement_testdoc`
--

LOCK TABLES `tb_project_requirement_testdoc` WRITE;
/*!40000 ALTER TABLE `tb_project_requirement_testdoc` DISABLE KEYS */;
/*!40000 ALTER TABLE `tb_project_requirement_testdoc` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tb_project_type`
--

DROP TABLE IF EXISTS `tb_project_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_project_type` (
  `id` char(21) NOT NULL,
  `overflow` int NOT NULL COMMENT '记录业务文档的总字数是否超出token限制',
  PRIMARY KEY (`id`),
  CONSTRAINT `tb_project_type_tb_test_project_null_fk` FOREIGN KEY (`id`) REFERENCES `tb_test_project` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用来记录该项目采用何种方式处理业务文档';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_project_type`
--

LOCK TABLES `tb_project_type` WRITE;
/*!40000 ALTER TABLE `tb_project_type` DISABLE KEYS */;
/*!40000 ALTER TABLE `tb_project_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tb_test_project`
--

DROP TABLE IF EXISTS `tb_test_project`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_test_project` (
  `id` char(21) NOT NULL COMMENT 'use snowflake method to generate unique id',
  `name` varchar(100) NOT NULL COMMENT 'project name',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='save the basic info of project to use llm to test';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_test_project`
--

LOCK TABLES `tb_test_project` WRITE;
/*!40000 ALTER TABLE `tb_test_project` DISABLE KEYS */;
/*!40000 ALTER TABLE `tb_test_project` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tb_project_workflow_artifact`
--

DROP TABLE IF EXISTS `tb_project_workflow_artifact`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_project_workflow_artifact` (
  `project_id` varchar(21) NOT NULL,
  `artifact_key` varchar(80) NOT NULL,
  `input_hash` char(64) NOT NULL,
  `source_revision` char(64) NOT NULL,
  `prompt_version` varchar(32) NOT NULL,
  `model_label` varchar(32) NOT NULL,
  `content` longtext NOT NULL,
  `metadata_json` text NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`project_id`,`artifact_key`,`input_hash`,`source_revision`,`prompt_version`,`model_label`),
  INDEX `idx_workflow_artifact_project_key` (`project_id`,`artifact_key`),
  CONSTRAINT `fk_workflow_artifact_project` FOREIGN KEY (`project_id`) REFERENCES `tb_test_project` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_project_workflow_artifact`
--

LOCK TABLES `tb_project_workflow_artifact` WRITE;
/*!40000 ALTER TABLE `tb_project_workflow_artifact` DISABLE KEYS */;
/*!40000 ALTER TABLE `tb_project_workflow_artifact` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2024-06-13 13:57:29
