import { PrismaClient } from "@prisma/client"
import bcrypt from "bcryptjs"

const prisma = new PrismaClient()

async function main() {
  console.log("🌱 Seeding database...")

  // Create admin user
  const hashedPassword = await bcrypt.hash("admin123", 12)
  const admin = await prisma.user.upsert({
    where: { email: "admin@ifpi.org" },
    update: {},
    create: {
      name: "IFPI Admin",
      email: "admin@ifpi.org",
      password: hashedPassword,
      role: "ADMIN",
    },
  })
  console.log("✅ Admin user:", admin.email)

  // Create learner
  const learner = await prisma.user.upsert({
    where: { email: "learner@ifpi.org" },
    update: {},
    create: {
      name: "Test Learner",
      email: "learner@ifpi.org",
      password: await bcrypt.hash("learner123", 12),
      role: "LEARNER",
    },
  })
  console.log("✅ Learner user:", learner.email)

  // Create academy
  const academy = await prisma.academy.upsert({
    where: { slug: "ifpi-main" },
    update: {},
    create: {
      name: "IFPI Main Academy",
      slug: "ifpi-main",
      description: "The primary training portal for IFPI members",
    },
  })
  console.log("✅ Academy:", academy.name)

  // Create sample course
  const existingCourse = await prisma.course.findFirst({ where: { title: "IFPI Fundamentals" } })
  if (!existingCourse) {
    const course = await prisma.course.create({
      data: {
        title: "IFPI Fundamentals",
        description: "An introduction to the International Federation of the Phonographic Industry, its mission, structure, and key programs.",
        category: "Foundation",
        isPublished: true,
        passingScore: 70,
        duration: 45,
        createdById: admin.id,
        coverColor: "bg-blue-500",
        slides: {
          create: [
            { title: "Welcome to IFPI", content: "<h2>Welcome to IFPI Fundamentals</h2><p>This course will give you a comprehensive overview of IFPI — who we are, what we do, and how we support the global recorded music industry.</p><p>By the end of this course you will understand IFPI's key programs, our global advocacy work, and how member companies benefit from our services.</p>", slideType: "TEXT", order: 1 },
            { title: "What is IFPI?", content: "<h2>What is IFPI?</h2><p>IFPI (International Federation of the Phonographic Industry) is the organization that promotes the interests of the recording industry worldwide.</p><ul><li>Represents over 8,000 record labels</li><li>Active in 66 countries</li><li>Founded in 1933</li><li>Headquartered in London</li></ul>", slideType: "TEXT", order: 2 },
            { title: "Our Mission", content: "<h2>IFPI's Mission</h2><p>We promote the interests of the recording industry worldwide in three core areas:</p><ol><li><strong>Licensing</strong> — Ensuring rights are properly licensed</li><li><strong>Anti-piracy</strong> — Combating illegal copying and distribution</li><li><strong>Government relations</strong> — Advocating for fair copyright laws</li></ol>", slideType: "TEXT", order: 3 },
            { title: "Global Music Report", content: "<h2>Global Music Report</h2><p>Each year IFPI publishes the Global Music Report — the definitive source of data on the international recorded music market.</p><p>Key findings from our latest report:</p><ul><li>Streaming now represents 67% of global revenues</li><li>Physical music grew for the third consecutive year</li><li>Over 600 million people subscribe to audio streaming services</li></ul>", slideType: "TEXT", order: 4 },
            { title: "Summary & Next Steps", content: "<h2>Congratulations!</h2><p>You've completed the IFPI Fundamentals overview. You now have a solid understanding of:</p><ul><li>IFPI's mission and history</li><li>Our global membership</li><li>Key industry programs</li></ul><p>Next, take the <strong>IFPI Fundamentals Assessment</strong> to earn your certificate.</p>", slideType: "TEXT", order: 5 },
          ],
        },
      },
    })
    console.log("✅ Course:", course.title)

    // Create sample exam
    const exam = await prisma.exam.create({
      data: {
        title: "IFPI Fundamentals Assessment",
        description: "Test your knowledge of IFPI's mission and structure.",
        instructions: "Read each question carefully. You have 15 minutes and 3 attempts.",
        passingScore: 70,
        timeLimit: 15,
        maxAttempts: 3,
        isPublished: true,
        category: "Foundation",
        createdById: admin.id,
        questions: {
          create: [
            {
              text: "What does IFPI stand for?",
              questionType: "MULTIPLE_CHOICE",
              options: JSON.stringify(["International Federation of the Phonographic Industry", "International Foundation for Performing Industry", "International Forum for Publishing Interests", "International Fund for Phonographic Innovation"]),
              correctAnswer: "0",
              points: 1,
              order: 1,
            },
            {
              text: "In which year was IFPI founded?",
              questionType: "MULTIPLE_CHOICE",
              options: JSON.stringify(["1920", "1933", "1945", "1960"]),
              correctAnswer: "1",
              points: 1,
              order: 2,
            },
            {
              text: "Where is IFPI headquartered?",
              questionType: "MULTIPLE_CHOICE",
              options: JSON.stringify(["New York", "Paris", "London", "Geneva"]),
              correctAnswer: "2",
              points: 1,
              order: 3,
            },
            {
              text: "Streaming represents the majority of global music revenues.",
              questionType: "TRUE_FALSE",
              options: JSON.stringify(["True", "False"]),
              correctAnswer: "0",
              points: 1,
              order: 4,
            },
          ],
        },
      },
    })
    console.log("✅ Exam:", exam.title)
  }

  console.log("\n🎉 Seed complete!")
  console.log("\n📋 Login credentials:")
  console.log("  Admin:   admin@ifpi.org  /  admin123")
  console.log("  Learner: learner@ifpi.org  /  learner123")
}

main()
  .catch(e => { console.error(e); process.exit(1) })
  .finally(() => prisma.$disconnect())
