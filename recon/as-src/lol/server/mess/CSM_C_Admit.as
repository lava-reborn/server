class lol.server.mess.CSM_C_Admit extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_C_Admit(char, perm, post)
   {
      super();
      this._name = "admit";
      this.addProp("post",post);
      this.addProp("perm",perm);
      this.addProp("char",char);
   }
}
