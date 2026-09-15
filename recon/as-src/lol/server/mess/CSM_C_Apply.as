class lol.server.mess.CSM_C_Apply extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_C_Apply(number, action)
   {
      super();
      this._name = "apply";
      this.addProp("action",action);
      this.addProp("number",number);
   }
}
