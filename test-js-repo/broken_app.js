
function greet(user) {
    // BUG: Accessing property of undefined
    console.log("Hello, " + user.profile.name);
}

// Simulate production crash
console.log("App starting...");
try {
    greet(null); // This will crash
} catch (e) {
    console.error(e.stack);
    process.exit(1);
}
