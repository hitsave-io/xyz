-- A better function for authorizing users. It converts from an API key (which is always unique in 
-- the database), to the UUID of the user who owns it. This is helpful, because user UUIDs are used 
-- throughout the rest of the schema to indicate ownership of a resource.

CREATE OR REPLACE FUNCTION user_from_key(IN key VARCHAR(64), OUT _result UUID)
AS
$BODY$
BEGIN
    SELECT u.id INTO _result
        FROM users u
        JOIN api_keys ak
        ON u.id = ak.user_id
        WHERE ak.key = $1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Invalid key %', $1 USING ERRCODE = 'invalid_password';
    END IF;

    RETURN;
END
$BODY$
LANGUAGE plpgsql;
