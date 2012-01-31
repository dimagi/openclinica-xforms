package org.openclinica.uconn;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.EditText;
import android.widget.Toast;

public class ClinicianLoginActivity extends Activity {

	String reportUrl;
	
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.clinlogin);

        reportUrl = getIntent().getExtras().getString("url");
    }
	
    public void logIn(View v) {
    	EditText pinField = (EditText)findViewById(R.id.pin);
    	String pin = pinField.getText().toString();
    	
    	if (!validatePIN(pin)) {
    		Toast toast = Toast.makeText(this, "Not a valid PIN", Toast.LENGTH_SHORT);
    		toast.show();
    		return;
    	}
    	
    	Intent i = new Intent(this, ResultsActivity.class);
    	i.putExtra("url", reportUrl);
    	startActivity(i);
    	finish();
    }
    
    private boolean validatePIN(String pin) {
    	return "4444".equals(pin);
    }
}