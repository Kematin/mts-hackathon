local function processString(str)
	local result = str
	result = result:lower()
	return result
end

local proccessed = processString("SoMe STring")
print(proccessed)