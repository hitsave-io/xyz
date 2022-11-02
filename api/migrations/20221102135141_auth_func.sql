-- Update the function for authorizing users. It now accepts another parameter, which 
-- is the possibly already-known user_id (UUID). If this is passed, the function
-- immediately returns it. If not, it attempts to get the user_id from the api_key.

CREATE OR REPLACE FUNCTION get_user_id(
    IN user_id UUID, 
    IN key VARCHAR(64), 
    OUT _result UUID)
AS
$BODY$
BEGIN
    IF $1 IS NOT NULL THEN
        SELECT id INTO _result
        FROM users
        WHERE id = $1;

    END IF;

    IF NOT FOUND THEN
        IF key IS NOT NULL THEN
            SELECT user_from_key(key) INTO _result;
        END IF;
    END IF;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unable to determine user from auth params.'
        USING ERRCODE = 'invalid_password';
    END IF;

    RETURN;
END
$BODY$
LANGUAGE plpgsql;
